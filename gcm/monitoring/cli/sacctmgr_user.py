# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass, field
from typing import (
    Any,
    Collection,
    Generator,
    Hashable,
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
from gcm.monitoring.dataclass_utils import instantiate_dataclass
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.client import SlurmCliClient, SlurmClient
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.slurm.sacctmgr_user import SacctmgrUserPayload
from typeguard import typechecked

LOGGER_NAME = "sacctmgr_user"
logger = logging.getLogger(LOGGER_NAME)  # default logger to be overridden in main()


def user_iterator(
    slurm_client: SlurmClient,
    cluster: str,
    collection_date: str,
    heterogeneous_cluster_v1: bool,
) -> Generator[SacctmgrUserPayload, None, None]:
    for user in slurm_client.sacctmgr_user():
        get_stdout = iter(slurm_client.sacctmgr_user_info(user))
        fields = next(get_stdout).strip().split("|")
        for user_info in get_stdout:
            values = user_info.strip().split("|")
            sacctmgr_user_data: dict[Hashable, str] = dict(zip(fields, values))
            sacctmgr_user_payload_dict: dict[Hashable, Any] = {
                "ds": collection_date,
                "cluster": cluster,
                "derived_cluster": get_derived_cluster(
                    data=sacctmgr_user_data,
                    heterogeneous_cluster_v1=heterogeneous_cluster_v1,
                    cluster=cluster,
                ),
                "sacctmgr_user": sacctmgr_user_data,
            }
            yield instantiate_dataclass(
                SacctmgrUserPayload, sacctmgr_user_payload_dict, logger=logger
            )


def collect_user(
    clock: Clock,
    cluster: str,
    slurm_client: SlurmClient,
    heterogeneous_cluster_v1: bool,
) -> Generator[SacctmgrUserPayload, None, None]:

    log_time = clock.unixtime()
    collection_date = unixtime_to_pacific_datetime(log_time).strftime("%Y-%m-%d")

    records = user_iterator(
        slurm_client,
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
    Collects slurm user information and sends to sink.
    """

    def collect_user_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[SacctmgrUserPayload, None, None]:
        return collect_user(
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
                collect_user_callable,
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
