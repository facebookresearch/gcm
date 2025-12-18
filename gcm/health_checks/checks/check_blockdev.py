# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import logging
import os
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from enum import auto, Enum
from typing import Any, Collection, Dict, List, NamedTuple, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.output_utils import CheckOutput, Metric
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import common_arguments, telemetry_argument
from gcm.health_checks.subprocess import shell_command
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from pydantic import BaseModel
from typeguard import typechecked

SHELL_CMD_TIMEOUT = 30


class BlockDeviceError(Enum):
    MISMAP = auto()
    HEALTH_LOG_INVALID = auto()
    SIZE_MISMATCH = auto()
    SPARE_SPACE_LOW = auto()
    LIFETIME_EXCEEDED = auto()
    CRITERION_WARNING = 100
    LIFETIME_LOW = auto()
    BAD_SMARTDATA = auto()
    OK = 200


class BlockDeviceData(NamedTuple):
    name: str
    model: str
    serial: str
    size: int
    health_log_status: bool
    read_kbytes: int
    written_kbytes: int
    host_reads: int
    host_writes: int
    percentage_used: int
    spare_available: int
    spare_threshold: int


class Disk(BaseModel):
    blockdev: str
    size: int


class DisksManifest(BaseModel):
    disks: Dict[str, Disk]


class BlockdevCheck(CheckEnv, Protocol):
    def read_manifest(self, manifest_file: str) -> Dict[str, Any]: ...

    def read_sysfs_dir(self, path: str) -> Optional[List[str]]: ...

    def read_smartdata(self, blockdev: str) -> Dict[Any, Any]: ...


@dataclass
class BlockdevCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def read_manifest(self, manifest_file: str) -> Dict[str, Any]:
        with open(manifest_file) as manifest:
            return json.loads(manifest.read())

    def read_sysfs_dir(self, path: str) -> Optional[List[str]]:
        try:
            return os.listdir(path)
        except Exception:
            return None

    def read_smartdata(self, blockdev: str) -> Dict[str, Any]:
        smartctl_out = shell_command(
            f"sudo /usr/sbin/smartctl -xj /dev/{blockdev}", SHELL_CMD_TIMEOUT
        )
        return json.loads(smartctl_out.stdout)


def _format_blockdev_issues(issue_list: List[Tuple[BlockDeviceError, str]]) -> str:
    return "; ".join(list(map(lambda x: f"{x[0].name}: {x[1]}", issue_list)))


def _enumerate_issues(
    disk_data: DisksManifest, bd_data: BlockDeviceData
) -> List[Tuple[BlockDeviceError, str]]:
    issues = []
    if not bd_data.health_log_status:
        return [
            (
                BlockDeviceError.HEALTH_LOG_INVALID,
                f"Unable to read health logs from drive {bd_data.name} (bd_data.serial)!",
            )
        ]
    if bd_data.size < disk_data.disks[bd_data.name].size:
        issues.append(
            (
                BlockDeviceError.SIZE_MISMATCH,
                f"{bd_data.name} ({bd_data.serial}) is undersized, size={bd_data.size} expected={disk_data.disks[bd_data.name].size}",
            )
        )
    if bd_data.percentage_used > 100:
        issues.append(
            (
                BlockDeviceError.LIFETIME_EXCEEDED,
                f"{bd_data.name} ({bd_data.serial}) is {bd_data.percentage_used}% used",
            )
        )
    elif bd_data.percentage_used > 80:
        issues.append(
            (
                BlockDeviceError.LIFETIME_LOW,
                f"{bd_data.name} ({bd_data.serial}) is {bd_data.percentage_used}% used",
            )
        )
    if bd_data.spare_available < bd_data.spare_threshold:
        issues.append(
            (
                BlockDeviceError.SPARE_SPACE_LOW,
                f"{bd_data.name} ({bd_data.serial}) has low spare space, {bd_data.spare_available} available, {bd_data.spare_threshold} threshold",
            )
        )
    if (bd_data.read_kbytes == 0 and bd_data.host_reads > 100) or (
        bd_data.written_kbytes == 0 and bd_data.host_writes > 100
    ):
        issues.append(
            (
                BlockDeviceError.BAD_SMARTDATA,
                f"{bd_data.name} ({bd_data.serial}) bytes read or written reports zero kb despite issued commands, suspected faulty disk reporting",
            )
        )
    return issues


def _parse_smart_data(slot_name: str, smart_data: Dict[str, Any]) -> BlockDeviceData:
    health_info = {
        "data_units_read": 0,
        "data_units_written": 0,
        "host_reads": 0,
        "host_writes": 0,
        "percentage_used": 0,
        "available_spare": 0,
        "available_spare_threshold": 0,
    }

    health_log_exists = (
        "nvme_smart_health_information_log" in smart_data
        and smart_data["nvme_smart_health_information_log"] is not {}
    )
    if health_log_exists:
        health_info = smart_data["nvme_smart_health_information_log"]

    bd_data = BlockDeviceData(
        name=slot_name,
        model=smart_data.get("model_name", ""),
        serial=smart_data.get("serial_number", ""),
        size=smart_data.get("nvme_total_capacity", 0),
        health_log_status=health_log_exists,
        read_kbytes=health_info["data_units_read"] * 512,
        written_kbytes=health_info["data_units_written"] * 512,
        # https://www.intel.com/content/dam/support/us/en/documents/solid-state-drives/Intel_SSD_Smart_Attrib_for_PCIe.pdf
        # Looks like most vendors are doing units of 1000 512-byte LBA equivalents
        host_reads=health_info["host_reads"],
        host_writes=health_info["host_writes"],
        percentage_used=health_info["percentage_used"],
        spare_available=health_info["available_spare"],
        spare_threshold=health_info["available_spare_threshold"],
    )

    return bd_data


def _blockdev_data_to_metrics(bd_data: BlockDeviceData) -> List[Metric]:
    return [
        Metric(f"{bd_data.name}_serial", str(bd_data.serial)),
        Metric(f"{bd_data.name}_size", bd_data.size),
        Metric(f"{bd_data.name}_rkb", bd_data.read_kbytes),
        Metric(f"{bd_data.name}_wkb", bd_data.written_kbytes),
        Metric(f"{bd_data.name}_host_reads", bd_data.host_reads),
        Metric(f"{bd_data.name}_host_writes", bd_data.host_writes),
        Metric(
            f"{bd_data.name}_used",
            bd_data.percentage_used,
            units="%",
            metric_warn="80",
            metric_crit="100",
        ),
        Metric(
            f"{bd_data.name}_spare",
            bd_data.spare_available,
            units="%",
            metric_crit=f"{bd_data.spare_threshold}:",
        ),
    ]


def process_check_blockdev(obj: BlockdevCheck, manifest: Dict[str, Any]) -> CheckOutput:
    check_out = CheckOutput("check_blockdev")

    disk_manifest = DisksManifest(disks=manifest["disks"])

    disk_count = len(disk_manifest.disks.keys())

    check_out.short_metrics = [
        Metric(
            "block_devices",
            disk_count,
            metric_min=str(disk_count),
        ),
    ]

    def _read_and_parse_smartdata(disk_entry: Tuple[str, Disk]) -> BlockDeviceData:
        slot = disk_entry[0]
        tmp_disk_manifest = disk_entry[1]
        smartctl_data = obj.read_smartdata(tmp_disk_manifest.blockdev)
        return _parse_smart_data(slot, smartctl_data)

    drives = disk_manifest.disks.items()
    blockdata_list = list(map(_read_and_parse_smartdata, drives))

    check_out.long_metrics = list(map(_blockdev_data_to_metrics, blockdata_list))

    issues_by_disk = {
        blockdev_data.name: _enumerate_issues(disk_manifest, blockdev_data)
        for blockdev_data in blockdata_list
        if _enumerate_issues(disk_manifest, blockdev_data)
    }

    check_out.long_out = list(map(_format_blockdev_issues, issues_by_disk.values()))

    flattened_issues = [
        issue[0].value
        for slot_issues in issues_by_disk.values()
        for issue in slot_issues
    ]

    most_critical_issue_value = min(flattened_issues, default=BlockDeviceError.OK.value)

    if issues_by_disk:
        check_out.short_out = (
            f'Block device(s) unhealthy: {",".join(issues_by_disk.keys())}'
        )

    if most_critical_issue_value < BlockDeviceError.CRITERION_WARNING.value:
        check_out.check_status = ExitCode.CRITICAL
    elif most_critical_issue_value < BlockDeviceError.OK.value:
        check_out.check_status = ExitCode.CRITICAL
    else:
        check_out.check_status = ExitCode.OK

    return check_out


@click.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--manifest_file", default="/etc/manifest.json")
@click.pass_obj
@typechecked
def check_blockdev(
    obj: Optional[BlockdevCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    manifest_file: str,
) -> None:
    """Check block devices against the manifest file"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check-blockdev: cluster: {cluster}, node: {node}, type: {type} manifest file: {manifest_file}"
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

    if obj is None:
        obj = BlockdevCheckImpl(cluster, type, log_level, log_folder)

    exit_code = ExitCode.UNKNOWN
    msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.CHECK_BLOCKDEV.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_BLOCKDEV,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_blockdev():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_BLOCKDEV.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        node_manifest: Dict[str, Any] = {}
        try:
            node_manifest = obj.read_manifest(manifest_file)
            check = process_check_blockdev(obj, node_manifest)
            exit_code = check.check_status
            if exit_code != ExitCode.OK:
                msg = str(check)
            else:
                msg = "blockdev passes"
        except Exception as e:
            exit_code = ExitCode.WARN
            msg = f"Exception occurred: {e}"

        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)
