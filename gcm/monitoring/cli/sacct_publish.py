# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import io
import logging
import sys
import traceback
from dataclasses import dataclass, field
from datetime import tzinfo
from typing import (
    Collection,
    Generator,
    Hashable,
    List,
    Mapping,
    Optional,
    Protocol,
    runtime_checkable,
)

import click
import clusterscope
from gcm.exporters import registry

from gcm.monitoring.click import (
    chunk_size_option,
    click_default_cmd,
    cluster_option,
    dry_run_option,
    heterogeneous_cluster_v1_option,
    log_folder_option,
    log_level_option,
    retries_option,
    sink_option,
    sink_opts_option,
    stdout_option,
    Timezone,
)
from gcm.monitoring.clock import (
    Clock,
    ClockImpl,
    PT,
    time_to_time_aware,
    tz_aware_fromisoformat,
)
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.constants import SLURM_CLI_DELIMITER

from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.slurm.sacct import SacctPayload
from typeguard import typechecked
from typing_extensions import Literal


LOGGER_NAME = "sacct_publish"

logger: logging.Logger = logging.getLogger(
    LOGGER_NAME
)  # default logger to be overridden in main()


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...


@dataclass
class CliObjectImpl:
    clock: Clock = field(default_factory=ClockImpl)
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)

    def cluster(self) -> str:
        return clusterscope.cluster()


_default_obj: CliObject = CliObjectImpl()


def print_tb(verbose: bool) -> None:
    if not verbose:
        return

    exc_info = sys.exc_info()
    assert all(
        i is not None for i in exc_info
    ), "Can only be called in an exception handler"
    traceback.print_exception(*exc_info)


@click_default_cmd(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "obj": _default_obj,
    },
)
@cluster_option
@sink_option
@sink_opts_option
@log_level_option
@log_folder_option
@stdout_option
@heterogeneous_cluster_v1_option
@click.argument("sacct_output", type=click.File("r"), default="-")
@dry_run_option
@chunk_size_option
@retries_option
@click.option(
    "--ignore-line-errors",
    is_flag=True,
    help=(
        "Ignore lines with invalid input instead of throwing an error. "
        "Since sacct does not properly escape newlines or pipe characters, there may "
        "be lines which contain fewer or more fields than there are headers, causing "
        "the script to parse them incorrectly."
    ),
)
@click.option(
    "--sacct-output-io-errors",
    type=click.Choice(["strict", "ignore", "replace"]),
    default="strict",
    show_default=True,
    help=(
        "Choose what to do with UTF-8 decoding errors in SACCT_OUTPUT. "
        "Refer to the official Python documentation for `open` to understand what "
        "these modes do: https://docs.python.org/3/library/codecs.html#error-handlers"
    ),
)
@click.option(
    "--delimiter",
    default=SLURM_CLI_DELIMITER,
    show_default=True,
    help="ASCII character used to delimit fields when using -p or -P",
)
@click.option(
    "--sacct-timezone",
    default=None,
    show_default=True,
    type=Timezone(),
    help=(
        "timezone of the system that generated sacct output, needs to follow tz database (https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)"
        "If omitted, uses current system's timezone."
    ),
)
@click.pass_obj
@typechecked
def main(
    obj: CliObject,
    cluster: Optional[str],
    sink: str,
    sink_opts: Collection[str],
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    stdout: bool,
    heterogeneous_cluster_v1: bool,
    sacct_output: io.TextIOWrapper,
    chunk_size: int,
    dry_run: bool,
    retries: int,
    ignore_line_errors: bool,
    sacct_output_io_errors: Literal["strict", "ignore", "replace"],
    delimiter: str,
    sacct_timezone: Optional[tzinfo],
) -> None:
    """Take the output of sacct SACCT_OUTPUT in the "parsable2" format and write it
    to a sink

    SACCT_OUTPUT is a file path. If omitted, then file is read from STDIN.

    The "End" field is used to partition the data by day, and it is expected to be in
    the format "%Y-%m-%dT%H:%M:%S" (see [1] for details on the format specification).
    """
    # Occasionally, user-defined sacct fields (e.g. comment, job name) are not valid
    # utf-8, so we allow the user to choose what should be done in this case
    sacct_output.reconfigure(errors=sacct_output_io_errors)
    fields = sacct_output.readline().strip().split(delimiter)
    # TODO: remove log time from `SacctPayload` dataclass, `Log` dataclass already has log time
    log_time = obj.clock.unixtime()

    def sacct_generator_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[SacctPayload, None, None]:
        return generate_sacct_records(
            sacct_output=sacct_output,
            fields=fields,
            ignore_line_errors=ignore_line_errors,
            cluster=cluster,
            delimiter=delimiter,
            sacct_timezone=sacct_timezone,
            log_time=log_time,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
            logger=logger,
        )

    run_data_collection_loop(
        logger_name=LOGGER_NAME,
        log_folder=log_folder,
        stdout=stdout,
        log_level=log_level,
        cluster=obj.cluster() if cluster is None else cluster,
        clock=obj.clock,
        once=True,
        interval=1,
        data_collection_tasks=[
            (
                sacct_generator_callable,
                SinkAdditionalParams(
                    data_type=DataType.LOG,
                    heterogeneous_cluster_v1=heterogeneous_cluster_v1,
                ),
            ),
        ],
        sink=sink,
        sink_opts=sink_opts,
        retries=retries,
        chunk_size=chunk_size,
        dry_run=dry_run,
        registry=obj.registry,
    )


def generate_sacct_records(
    sacct_output: io.TextIOWrapper,
    fields: List[str],
    ignore_line_errors: bool,
    cluster: str,
    delimiter: str,
    sacct_timezone: Optional[tzinfo],
    log_time: int,
    heterogeneous_cluster_v1: bool,
    logger: logging.Logger,
) -> Generator[SacctPayload, None, None]:
    i, record_count = 0, 0
    # Start from 2 because we read the header and line numbers start from 1
    for i, line in enumerate(sacct_output, start=2):
        try:
            yield to_payload(
                fields,
                line,
                (cluster),
                delimiter,
                sacct_timezone,
                log_time,
                heterogeneous_cluster_v1,
            )
            record_count += 1
        except ValueError as error:
            if ignore_line_errors:
                logger.warning(f"Skipping invalid input on line {i}", exc_info=True)
                continue
            raise ValueError(f"Invalid input on line {i}.") from error
    logger.debug(f"Processed {i} lines for {record_count} records")


def to_payload(
    fields: List[str],
    sacct_line: str,
    cluster: str,
    delimiter: str,
    sacct_timezone: Optional[tzinfo],
    log_time: int,
    heterogeneous_cluster_v1: bool,
) -> SacctPayload:
    """Convert a line of sacct output to a message payload."""
    values = sacct_line.strip().split(delimiter)
    if len(fields) != len(values):
        raise ValueError(
            f"Length of fields ({len(fields)}) != length of values ({len(values)})"
        )
    sacct_data: dict[Hashable, str] = dict(zip(fields, values))
    derived_cluster = get_derived_cluster(
        data=sacct_data,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        cluster=cluster,
    )
    sacct_data["Eligible"] = time_to_time_aware(sacct_data["Eligible"], sacct_timezone)
    sacct_data["Start"] = time_to_time_aware(sacct_data["Start"], sacct_timezone)
    sacct_data["Submit"] = time_to_time_aware(sacct_data["Submit"], sacct_timezone)
    end_time = tz_aware_fromisoformat(sacct_data["End"], sacct_timezone)
    sacct_data["End"] = end_time.isoformat()
    # ds should always be Pacific time (affected by Daylight savings)
    # more info: https://www.internalfb.com/intern/wiki/Dataswarm/Write_Pipeline/Hourly_Partitions/#background
    end_ds = end_time.astimezone(PT).strftime("%Y-%m-%d")
    return SacctPayload(
        time=log_time,
        end_ds=end_ds,
        cluster=cluster,
        derived_cluster=derived_cluster,
        sacct=sacct_data,
    )
