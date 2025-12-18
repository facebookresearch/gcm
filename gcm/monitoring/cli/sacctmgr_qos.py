# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass, field
from typing import (
    Collection,
    Hashable,
    Iterable,
    List,
    Literal,
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
    interval_option,
    log_folder_option,
    log_level_option,
    once_option,
    retries_option,
    sink_option,
    sink_opts_option,
    stdout_option,
)
from gcm.monitoring.clock import Clock, ClockImpl, unixtime_to_pacific_datetime
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.client import SlurmCliClient, SlurmClient
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.slurm.sacctmgr_qos import SacctmgrQosPayload
from typeguard import typechecked

LOGGER_NAME = "sacctmgr_qos"
logger = logging.getLogger(LOGGER_NAME)  # default logger to be overridden in main()


def to_payload(
    fields: List[str],
    sacctmgr_qos_line: str,
    cluster: str,
    collection_date: str,
    heterogeneous_cluster_v1: bool,
) -> SacctmgrQosPayload:
    """Convert a line of sacctmgr show qos output to a message payload."""
    values = sacctmgr_qos_line.strip().split("|")

    sacctmgr_qos_data: dict[Hashable, str] = dict(zip(fields, values))
    return SacctmgrQosPayload(
        ds=collection_date,
        cluster=cluster,
        sacctmgr_qos=sacctmgr_qos_data,
        derived_cluster=get_derived_cluster(
            data=sacctmgr_qos_data,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
            get_partition_from_qos=True,
            cluster=cluster,
        ),
    )


def qos_iterator(
    fields: List[str],
    stdout: Iterable[str],
    cluster: str,
    collection_date: str,
    heterogeneous_cluster_v1: bool,
) -> Iterable[SacctmgrQosPayload]:
    for line in stdout:
        yield to_payload(
            fields,
            line,
            cluster,
            collection_date,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        )


def collect_qos(
    clock: Clock,
    cluster: str,
    slurm_client: SlurmClient,
    heterogeneous_cluster_v1: bool,
) -> Iterable[SacctmgrQosPayload]:

    log_time = clock.unixtime()
    collection_date = unixtime_to_pacific_datetime(log_time).strftime("%Y-%m-%d")

    get_stdout = iter(slurm_client.sacctmgr_qos())
    fields = next(get_stdout).strip().split("|")

    records = qos_iterator(
        fields,
        get_stdout,
        cluster,
        collection_date,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
    )

    return records


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...
    @property
    def slurm_client(self) -> SlurmClient: ...


@dataclass
class CliObjectImpl:
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)
    clock: Clock = field(default_factory=ClockImpl)
    slurm_client: SlurmClient = field(default_factory=SlurmCliClient)

    def cluster(self) -> str:
        return clusterscope.cluster()


# construct at module-scope because printing sink documentation relies on the object
_default_obj: CliObject = CliObjectImpl()


@click_default_cmd(context_settings={"obj": _default_obj})
@cluster_option
@sink_option
@sink_opts_option
@log_level_option
@log_folder_option
@stdout_option
@heterogeneous_cluster_v1_option
@interval_option(default=86400)
@once_option
@retries_option
@dry_run_option
@chunk_size_option
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
    interval: int,
    once: bool,
    retries: int,
    dry_run: bool,
    chunk_size: int,
) -> None:
    """
    Collects slurm QOS information and sends to sink.
    """

    def collect_qos_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Iterable[SacctmgrQosPayload]:
        return collect_qos(
            clock=obj.clock,
            cluster=cluster,
            slurm_client=obj.slurm_client,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
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
                collect_qos_callable,
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
