# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
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
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.client import SlurmCliClient, SlurmClient
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.slurm.scontrol import Scontrol

from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

LOGGER_NAME = "scontrol"
logger: logging.Logger  # initialization in main()

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


# construct at module-scope because printing sink documentation relies on the object
_default_obj: CliObject = CliObjectImpl()


def collect_scontrol(
    slurm_client: SlurmClient,
    cluster: str,
    heterogeneous_cluster_v1: bool,
    logger: logging.Logger,
) -> Generator[DataclassInstance, None, None]:
    attributes: dict[Hashable, str | int] = {
        "cluster": cluster,
    }
    scontrol_info = kv_as_messages(
        schema=Scontrol,
        lines=slurm_client.scontrol_partition(),
        attributes=attributes,
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        logger=logger,
    )

    return scontrol_info


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
    Collects slurm scontrol partition information and sends to sink.
    """

    def collect_scontrol_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[DataclassInstance, None, None]:
        return collect_scontrol(
            slurm_client=obj.slurm_client,
            cluster=cluster,
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
        once=once,
        interval=interval,
        data_collection_tasks=[
            (
                collect_scontrol_callable,
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


def kv_as_messages(
    schema: Type[_TDataclass],
    lines: Iterable[str],
    cluster: str,
    heterogeneous_cluster_v1: bool,
    logger: logging.Logger,
    attributes: Optional[dict[Hashable, str | int]] = None,
) -> Generator[_TDataclass, None, None]:
    for line in lines:
        formated_line = line.strip().split(" ")
        message: dict[Hashable, str | int] = {**(attributes or {})}
        for item in formated_line:
            k, v = item.strip().split("=", 1)
            message[k] = v
        message["derived_cluster"] = get_derived_cluster(
            data=message,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
            cluster=cluster,
        )
        yield instantiate_dataclass(schema, message, logger=logger)
