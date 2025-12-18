# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import re
from dataclasses import dataclass, field, fields
from itertools import chain
from pathlib import Path
from typing import (
    Callable,
    Collection,
    Dict,
    Generator,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Protocol,
    runtime_checkable,
    TYPE_CHECKING,
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
from gcm.monitoring.sink.protocol import (
    DataIdentifier,
    DataType,
    SinkAdditionalParams,
    SinkImpl,
)
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.storage import StorageCliClient, StorageClient
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.storage.mount import MountInfo
from gcm.schemas.storage.pure import PureInfo
from gcm.schemas.storage.statvfs import Statvfs
from typeguard import typechecked

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

LOGGER_NAME = "storage"


logger: logging.Logger  # initialization in main()


def get_statvfs_as_dict(dir: str) -> Dict[str, int]:
    statvfs_data = os.statvfs(dir)
    return {
        field.name: int(getattr(statvfs_data, field.name))
        for field in fields(Statvfs)
        if hasattr(statvfs_data, field.name)
    }


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...

    @property
    def storage_client(self) -> StorageClient: ...


@dataclass
class CliObjectImpl:
    clock: Clock = field(default_factory=ClockImpl)
    storage_client: StorageClient = field(default_factory=StorageCliClient)
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)

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
@click.option(
    "--statvfs-patterns",
    multiple=True,
    help=("Regex pattern for selecting directories from statvfs."),
)
@dry_run_option
@retries_option
@once_option
@chunk_size_option
@click.option(
    "--statvfs-symlink",
    default=None,
    help="Directory to look for statvfs symlinks.",
)
@click.option(
    "--pure-json-file-path",
    "pure_json_file_path",
    multiple=True,
    help="""File path to Json file with Pure information. It's expected that each line has the shape: {"user":"<user_id>","used":123,"sample_time":1757971817,"directory":"/path/"}""",
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
    interval: int,
    statvfs_patterns: Collection[str],
    dry_run: bool,
    retries: int,
    once: bool,
    chunk_size: int,
    statvfs_symlink: Optional[str],
    pure_json_file_path: tuple[str, ...],
) -> None:
    """
    Collects slurm storage partition information and sends to sink.
    """
    symlink_mapping = None
    if statvfs_symlink is not None:
        symlink_mapping = obj.storage_client.get_all_symlink_info(path="/")

    def _collect_statvfs(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[Statvfs, None, None]:
        statvfs_pattern = {
            item.split("=")[0]: item.split("=")[1] for item in statvfs_patterns
        }[
            cluster  # type: ignore[index]
        ]
        logger.info("collecting statvfs data with pattern: {}".format(statvfs_pattern))
        statvfs_info = as_statvfs_messages(
            statvfs_pattern=statvfs_pattern,
            cluster=cluster,  # type: ignore[arg-type]
            lines=obj.storage_client.get_all_mount_info(),
            get_statvfs=get_statvfs_as_dict,
            symlink_mapping=symlink_mapping,
        )
        return statvfs_info

    def _collect_pure(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[PureInfo, None, None]:
        pure_info_iterables = []
        assert pure_json_file_path is not None
        for path in pure_json_file_path:
            pure_info_iterables.append(obj.storage_client.get_pure_json(path, cluster))
        pure_info_combined = chain.from_iterable(pure_info_iterables)
        return yield_from(lines=pure_info_combined)

    data_collection_tasks: list[
        tuple[
            Callable[[str, int, logging.Logger], Iterable[DataclassInstance]],
            SinkAdditionalParams,
        ]
    ] = []

    if statvfs_patterns:
        data_collection_tasks.append(
            (
                _collect_statvfs,
                SinkAdditionalParams(
                    data_type=DataType.LOG, data_identifier=DataIdentifier.STATVFS
                ),
            ),
        )

    if pure_json_file_path:
        data_collection_tasks.append(
            (
                _collect_pure,
                SinkAdditionalParams(
                    data_type=DataType.LOG, data_identifier=DataIdentifier.PURE
                ),
            )
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
        data_collection_tasks=data_collection_tasks,
        sink=sink,
        sink_opts=sink_opts,
        retries=retries,
        chunk_size=chunk_size,
        dry_run=dry_run,
        registry=obj.registry,
    )


def as_statvfs_messages(
    statvfs_pattern: str,
    cluster: str,
    lines: Iterable[MountInfo],
    get_statvfs: Callable[[str], Dict[str, int]],
    symlink_mapping: Optional[Dict[Path, Path]],
) -> Generator[Statvfs, None, None]:
    for line in lines:
        fs_partition = line.mount_source
        symlink_path = (
            symlink_mapping.get(line.mount_point) if symlink_mapping else None
        )
        fs_mount_point = (symlink_path or line.mount_point).as_posix()
        if re.match(statvfs_pattern, fs_mount_point):
            message = Statvfs(
                cluster=cluster,
                directory=fs_mount_point,
                file_system=fs_partition,
                **get_statvfs(fs_mount_point),
            )
            yield message


def yield_from(lines: Iterable[PureInfo]) -> Generator[PureInfo, None, None]:
    yield from lines
