# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    piped_shell_command,
    PipedShellCommandOut,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


@click.group()
def check_storage() -> None:
    """storage based checks. i.e. disk space, mounted folders"""


class StorageCheck(CheckEnv, Protocol):
    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool: ...

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool: ...

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]: ...

    def get_disk_size(
        self, timeout_secs: int, volume: str, units: str, logger: logging.Logger
    ) -> PipedShellCommandOut: ...


@dataclass
class StorageCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_disk_usage(
        self, timeout_secs: int, volume: str, logger: logging.Logger
    ) -> ShellCommandOut:
        """Invoke df command to get the usage of the selected volume"""
        cmd = f"df --output=pcent,ipcent {volume}"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_mount_status(
        self, timeout_secs: int, dir: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        """Check if the directory is mounted"""
        logger.info(f"Running command `mount | grep {dir}")
        return piped_shell_command(["mount", f"grep {dir}"], timeout_secs)

    def check_file_exists(self, f: str, logger: logging.Logger) -> bool:
        logger.info(f"Checking existance of file: {f}")
        return Path(f).is_file()

    def check_directory_exists(self, dir: str, logger: logging.Logger) -> bool:
        logger.info(f"Checking existance of directory: {dir}")
        return Path(dir).is_dir()

    def get_fstab_mount_info(
        self, timeout_secs: int, mountpoint: str, logger: logging.Logger
    ) -> Tuple[ShellCommandOut, ShellCommandOut]:
        """Check if the mountpoint for fstab and mounts has the same entries"""
        cmd1 = f"awk '{mountpoint} {{print $2 | \"sort\"}}' /etc/fstab"
        logger.info(f"Running command: {cmd1}")

        cmd2 = f"awk '{mountpoint} {{print $2 | \"sort\"}}' /proc/mounts"
        logger.info(f"Running command: {cmd2}")

        return shell_command(cmd1, timeout_secs), shell_command(cmd2, timeout_secs)

    def get_disk_size(
        self, timeout_secs: int, volume: str, units: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        df_cmd = f"df --output=size -B {units} {volume}"
        logger.info(f"Running command `{df_cmd}`")
        return piped_shell_command(
            [
                df_cmd,
                # Remove `df` headers
                "sed 1d",
            ],
            timeout_secs,
        )


def process_disk_usage(
    output: str,
    error_code: int,
    warning_thr: int,
    critical_thr: int,
    inode_check: bool,
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"disk usage command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    msg = ""
    exit_code = ExitCode.OK
    try:
        text = output.splitlines()
        text = text[1].split("%")
        if inode_check:
            used_disk = int(text[1].strip())
        else:
            used_disk = int(text[0].strip())
    except Exception:
        return ExitCode.WARN, f"Invalid disk usage output: {output}.\n"

    if used_disk > critical_thr:
        exit_code = ExitCode.CRITICAL
        msg = f"Disk usage, {used_disk}%, is above critical threshold of {critical_thr}%.\n"
    elif used_disk > warning_thr:
        exit_code = ExitCode.WARN
        msg = (
            f"Disk usage, {used_disk}%, is above warning threshold of {warning_thr}%.\n"
        )

    if exit_code == ExitCode.OK:
        msg = f"Disk usage, {used_disk}%, is within limits.\n"
    return exit_code, msg


def process_mount_status(
    output: str,
    error_code: int,
) -> Tuple[ExitCode, str]:
    msg: str = "directory is mounted.\n"
    exit_code: ExitCode = ExitCode.OK
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"mount command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    if len(output) == 0:
        return (
            ExitCode.CRITICAL,
            "directory is not mounted.\n",
        )
    return exit_code, msg


@check_storage.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--volume",
    "-v",
    type=click.Path(file_okay=False, readable=False),
    help="Volumes to check for free space",
    multiple=True,
    required=True,
)
@click.option(
    "--usage-critical-threshold",
    type=click.INT,
    default=85,
    help="Usage threshold that if it's exceeded a CRITICAL is returned",
)
@click.option(
    "--usage-warning-threshold",
    type=click.INT,
    default=80,
    help="Usage threshold that if it's exceeded a WARNING is returned",
)
@click.option(
    "--inode-check/--no-inode-check",
    default=False,
    help="Check Usage or I-Node usage",
    show_default=True,
)
@click.pass_obj
@typechecked
def disk_usage(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    volume: Tuple[str, ...],
    usage_critical_threshold: int,
    usage_warning_threshold: int,
    inode_check: bool,
) -> None:
    """Check the free space on the specified volumes"""

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.DISK_USAGE,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_disk_usage(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for vol in volume:
            try:
                disk_out: ShellCommandOut = obj.get_disk_usage(timeout, vol, rt.logger)
            except Exception as e:
                disk_out = handle_subprocess_exception(e)

            rt.logger.info(disk_out.stdout)
            exit_code, msg = process_disk_usage(
                disk_out.stdout,
                disk_out.returncode,
                usage_warning_threshold,
                usage_critical_threshold,
                inode_check,
            )
            overall_msg += f"Volume {vol}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg)


@check_storage.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--directory",
    "-d",
    type=click.Path(file_okay=False, readable=False),
    help="Directory to check if is mounted",
    multiple=True,
    required=True,
)
@click.pass_obj
@typechecked
def mounted_directory(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    directory: Tuple[str, ...],
) -> None:
    """Check if the specified directories are mounted"""

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.MOUNTED_DIR,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_mounted_dir(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for dir in directory:
            try:
                mount_out: PipedShellCommandOut = obj.get_mount_status(
                    timeout, dir, rt.logger
                )
            except Exception as e:
                exc_out = handle_subprocess_exception(e)
                mount_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

            exit_code, msg = process_mount_status(
                mount_out.stdout,
                mount_out.returncode[0],
            )
            overall_msg += f"Directory {dir}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg)


@check_storage.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--file",
    "-f",
    type=click.Path(file_okay=True, dir_okay=False, readable=False),
    help="File to check if it exists",
    multiple=True,
    required=True,
)
@click.option(
    "--should-not-exist",
    type=bool,
    help="Invert the check; check if the files do not exist",
    is_flag=True,
    required=False,
    default=False,
)
@click.pass_obj
@typechecked
def file_exists(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    file: Tuple[str, ...],
    should_not_exist: bool,
) -> None:
    """Check if the specified files exist"""

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.FILE_EXISTS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_file_exists(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for f in file:
            try:
                file_check_out: bool = obj.check_file_exists(f, rt.logger)
            except Exception as e:
                file_check_out = False
                overall_msg += f"Checking file {f}. Exception {e} was raised.\n"

            if not file_check_out:
                exit_code = ExitCode.OK if should_not_exist else ExitCode.CRITICAL
                overall_msg += f"File {f} not found."
            else:
                exit_code = ExitCode.CRITICAL if should_not_exist else ExitCode.OK
                overall_msg += f"File {f} found."

            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        if overall_exit_code == ExitCode.OK:
            if should_not_exist:
                overall_msg = "All files are absent."
            else:
                overall_msg = "All files are present."

        rt.finish(overall_exit_code, overall_msg)


@check_storage.command()
@common_arguments
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--directory",
    "-d",
    type=click.Path(file_okay=False, dir_okay=True, readable=False),
    help="Directory to check if it exists",
    multiple=True,
    required=True,
)
@click.pass_obj
@typechecked
def directory_exists(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    directory: Tuple[str, ...],
) -> None:
    """Check if the specified directories exist"""

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.DIR_EXISTS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_dir_exists(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for d in directory:
            try:
                dir_check_out: bool = obj.check_directory_exists(d, rt.logger)
            except Exception as e:
                dir_check_out = False
                overall_msg += f"Checking directory {d}. Exception {e} was raised.\n"

            if not dir_check_out:
                exit_code = ExitCode.CRITICAL
                overall_msg += f"Directory {d} not found."
            else:
                exit_code = ExitCode.OK

            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        if overall_exit_code == ExitCode.OK:
            overall_msg = "All directories are present."

        rt.finish(overall_exit_code, overall_msg)


def process_check_mountpoint(
    mount_out: Tuple[ShellCommandOut, ShellCommandOut],
) -> Tuple[ExitCode, str]:
    if mount_out[0].returncode > 0 or mount_out[1].returncode > 0:
        return ExitCode.WARN, "awk command failed for check mountpoint"

    fstab_out = mount_out[0].stdout.strip().splitlines()
    mounts_out = mount_out[1].stdout.strip().splitlines()

    missmatch = []
    for dir in fstab_out:
        if dir not in mounts_out:
            missmatch.append(dir)

    if len(missmatch) > 0:
        return ExitCode.CRITICAL, f"the following dirs are not mounted: {missmatch}"
    else:
        return ExitCode.OK, "fstab and mounts have the same entries"


@check_storage.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--mountpoint",
    type=click.STRING,
    help="Mountpoint to check between fstab and mounts",
    required=True,
    multiple=True,
)
@click.pass_obj
@typechecked
def check_mountpoint(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    mountpoint: Tuple[str, ...],
) -> None:
    """Check if the specified mountpoint has the same entries in fstab and mounts"""

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_MOUNTPOINT,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_mountpoint(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for m in mountpoint:
            try:
                mount_out: Tuple[ShellCommandOut, ShellCommandOut] = (
                    obj.get_fstab_mount_info(timeout, m, rt.logger)
                )
            except Exception as e:
                exc_out = handle_subprocess_exception(e)
                mount_out = exc_out, exc_out

            exit_code, msg = process_check_mountpoint(mount_out)

            overall_msg += f"Mountpoint {m}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg)


def process_disk_size(
    output: str,
    error_codes: List[int],
    operator: str,
    expected_value: int,
) -> Tuple[ExitCode, str]:
    if any(error_codes) or len(output) == 0:
        return (
            ExitCode.WARN,
            f"disk size command FAILED, error_codes: {error_codes} output: {output}\n",
        )

    msg = ""
    exit_code = ExitCode.OK
    try:
        # Remove trailing unit
        actual_value = int(output.strip()[:-1])
    except Exception:
        return ExitCode.WARN, f"Invalid disk usage output: {output}.\n"

    critical = False
    if operator == "<":
        critical = actual_value >= expected_value

    if operator == "=":
        critical = actual_value != expected_value

    if operator == ">":
        critical = actual_value <= expected_value

    if operator == ">=":
        critical = actual_value < expected_value

    if operator == "<=":
        critical = actual_value > expected_value

    if critical:
        exit_code = ExitCode.CRITICAL
        msg = f"Disk size, {actual_value} {operator} {expected_value}"

    if exit_code == ExitCode.OK:
        msg = f"Disk size {actual_value} is within {operator} {expected_value}"
    return exit_code, msg


@check_storage.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--volume",
    "-v",
    type=click.Path(file_okay=False, readable=False),
    help="Volume to check size",
    required=True,
)
@click.option(
    "--size-unit",
    type=click.Choice(["K", "M", "G", "T"]),
    default="K",
    help="Compare the size in what type of units?",
)
@click.option(
    "--operator",
    type=click.Choice([">", "<", "=", "<=", ">="]),
    help="Which comparsion operator to assert?",
    required=True,
)
@click.option(
    "--value",
    type=click.INT,
    required=True,
    help="Value to assert against the operator",
)
@click.pass_obj
@typechecked
def disk_size(
    obj: Optional[StorageCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    volume: str,
    size_unit: str,
    operator: str,
    value: int,
) -> None:
    """
    Check the size of the given disk
    """

    if obj is None:
        obj = StorageCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.DISK_SIZE,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_disk_size(),
    ) as rt:
        try:
            disk_out = obj.get_disk_size(timeout, volume, size_unit, rt.logger)
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            disk_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        rt.logger.info(disk_out.stdout)
        exit_code, msg = process_disk_size(
            disk_out.stdout,
            disk_out.returncode,
            operator=operator,
            expected_value=value,
        )

        overall_msg = f"Volume {volume}: {msg}"
        overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg)
