#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Read SLURM node information and publish the data to a sink"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from functools import partial
from typing import (
    Callable,
    Collection,
    Generator,
    Hashable,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Protocol,
    runtime_checkable,
    Type,
    TYPE_CHECKING,
    TypeVar,
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
    interval_option,
    log_folder_option,
    log_level_option,
    once_option,
    retries_option,
    sink_option,
    sink_opts_option,
    stdout_option,
)
from gcm.monitoring.clock import Clock, ClockImpl
from gcm.monitoring.dataclass_utils import instantiate_dataclass
from gcm.monitoring.sink.protocol import (
    DataIdentifier,
    DataType,
    SinkAdditionalParams,
    SinkImpl,
)
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.client import SlurmCliClient, SlurmClient
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.monitoring.utils.parsing.stdout import parse_delimited
from gcm.schemas.slurm.sinfo_node import NodeData
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

LOGGER_NAME = "slurm_job_monitor"

logger = logging.getLogger(LOGGER_NAME)  # default logger to be overridden in main()

_TDataclass = TypeVar("_TDataclass")


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...

    @property
    def slurm_client(self) -> SlurmClient: ...


@dataclass
class CliObjectImpl:
    clock: Clock = field(default_factory=ClockImpl)
    slurm_client: SlurmClient = field(default_factory=SlurmCliClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)

    def cluster(self) -> str:
        return clusterscope.cluster()


_default_obj: CliObject = CliObjectImpl()


@click_default_cmd(context_settings={"obj": _default_obj})
@cluster_option
@sink_option
@sink_opts_option
@log_level_option
@log_folder_option
@stdout_option
@heterogeneous_cluster_v1_option
@chunk_size_option
@retries_option
@interval_option(default=60)
@once_option
@dry_run_option
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
    chunk_size: int,
    retries: int,
    interval: int,
    once: bool,
    dry_run: bool,
) -> None:
    """Retrieve SLURM node and job metrics."""

    def get_node_info(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[DataclassInstance, None, None]:
        derived_cluster_fetcher = partial(
            get_derived_cluster,
            cluster=cluster,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        )
        attributes: dict[Hashable, str | int] = {
            "cluster": cluster,
        }
        collection_unixtime = obj.clock.unixtime()
        attributes["collection_unixtime"] = collection_unixtime
        return as_messages(
            schema=NodeData,
            delimiter="|",
            lines=obj.slurm_client.sinfo(),
            attributes=attributes,
            derived_cluster_fetcher=derived_cluster_fetcher,
            logger=logger,
        )

    def get_job_info(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Iterable[DataclassInstance]:
        derived_cluster_fetcher = partial(
            get_derived_cluster,
            cluster=cluster,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        )
        attributes: dict[Hashable, str | int] = {
            "cluster": cluster,
        }
        collection_unixtime = obj.clock.unixtime()
        attributes["collection_unixtime"] = collection_unixtime
        return obj.slurm_client.squeue(
            attributes=attributes,
            derived_cluster_fetcher=derived_cluster_fetcher,
            logger=logger,
        )

    run_data_collection_loop(
        logger_name=LOGGER_NAME,
        log_folder=log_folder,
        stdout=stdout,
        log_level=log_level,
        cluster=obj.cluster() if cluster is None else cluster,
        clock=obj.clock,
        once=once,
        interval=interval,
        data_collection_tasks=[
            (
                get_node_info,
                SinkAdditionalParams(
                    data_type=DataType.LOG, data_identifier=DataIdentifier.NODE
                ),
            ),
            (
                get_job_info,
                SinkAdditionalParams(
                    data_type=DataType.LOG, data_identifier=DataIdentifier.JOB
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


def as_messages(
    schema: Type[_TDataclass],
    delimiter: str,
    lines: Iterable[str],
    derived_cluster_fetcher: Callable[[dict[Hashable, str | int]], str],
    logger: logging.Logger,
    attributes: Optional[dict[Hashable, str | int | str]] = None,
) -> Generator[_TDataclass, None, None]:
    fieldnames, rows = parse_delimited(lines, schema, delimiter, logger)
    rows = list(rows)
    num_rows = len(rows)
    for row in rows:
        message: dict[Hashable, str | int] = {
            "num_rows": num_rows,
            **(attributes or {}),
        }
        for k, v in zip(fieldnames, row):
            message[k] = v
        message["derived_cluster"] = derived_cluster_fetcher(message)
        yield instantiate_dataclass(schema, message, logger=logger)
