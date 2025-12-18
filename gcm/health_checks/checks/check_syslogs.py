# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import re
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, List, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.check_utils.xid_error_codes import ErrorCause
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
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


@click.group()
def check_syslogs() -> None:
    """syslog based checks. i.e. dmesg, syslog errors"""


class Syslog(CheckEnv, Protocol):
    def get_link_flap_report(
        self, syslog_file: Path, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_xid_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_io_error_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...


@dataclass
class SyslogImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_link_flap_report(
        self, syslog_file: Path, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f'sudo grep -i "Lost Carrier" {syslog_file}'
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_xid_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        # Run this command piping the input of the first into the second: "dmesg | grep NVRM:.Xid"
        logger.info("Running command `dmesg | grep NVRM:.Xid`")
        dmesg_out = piped_shell_command(["dmesg", "grep NVRM:.Xid"], timeout_secs)

        return dmesg_out

    def get_io_error_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        # Run this command piping the input of the first into the second: "dmesg | awk..."
        cmd = [
            "dmesg",
            'awk \'/I.O error, dev nvme/ { gsub(/,/, ""); print $6 | "sort | uniq | xargs echo" }\'',
        ]
        logger.info(f"Running command {' | '.join(cmd)}")
        dmesg_out = piped_shell_command(
            cmd,
            timeout_secs,
        )
        return dmesg_out


def process_link_flap_output(output: str, error_code: int) -> Tuple[ExitCode, str]:
    if error_code > 1:
        return (
            ExitCode.WARN,
            f"link flap command FAILED to execute. error_code: {error_code} output: {output}",
        )
    msg: str = ""
    exit_code: ExitCode = ExitCode.OK
    text: List[str] = output.splitlines()
    for line in text:
        if "ib" in line:
            exit_code = ExitCode.CRITICAL
            msg += "ib link flap detected.\n"
        if "eth" in line:
            msg = "eth link flap detected.\n"
            if exit_code < ExitCode.WARN:
                exit_code = ExitCode.WARN

    if exit_code == ExitCode.OK:
        msg = "No link flaps were detected"

    return exit_code, msg


def parse_xid_error_code(msg: str) -> Optional[int]:
    """Parse one row of an XID error to extract the error code"""
    m = re.search("NVRM: Xid \\([^)]+\\): (\\d+)", msg)
    return None if m is None else int(m.group(1))


def process_xid_output(output: str, error_code: int) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"dmesg command FAILED to execute. error_code: {error_code} output: {output}",
        )
    msg: str = ""
    exit_code: ExitCode = ExitCode.OK
    seen_xids = set()
    for line in output.split("\n"):
        split_line = line.split(":", 1)
        if len(split_line) != 2:
            continue
        xid_error_code = parse_xid_error_code(line)
        if xid_error_code not in seen_xids:
            seen_xids.add(xid_error_code)
            xid_causes = ", ".join(ErrorCause.get_causes_for_xid(xid_error_code))
            if xid_error_code in ErrorCause.NON_CRITICAL_ERRORS:
                msg += f"non-critical XID error: {xid_error_code}, XID causes: {xid_causes}. "
                if exit_code < ExitCode.WARN:
                    exit_code = ExitCode.WARN
            else:
                exit_code = ExitCode.CRITICAL
                msg += f"XID error: {xid_error_code}, XID causes: {xid_causes}. "

    if exit_code == ExitCode.OK:
        msg = "No XID error was found."
    return exit_code, msg


def process_io_errors_output(output: str, error_code: int) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"dmesg command FAILED to execute. error_code: {error_code} output: {output}",
        )
    if output == "":
        exit_code: ExitCode = ExitCode.OK
        msg: str = "No IO errors detected."
    else:
        exit_code = ExitCode.CRITICAL
        msg = "IO error detected on: "
    for line in output.split("\n"):
        msg += line
    return exit_code, msg


@check_syslogs.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option("--syslog_file", default="/var/log/syslog")
@click.pass_obj
@typechecked
def link_flaps(
    obj: Optional[Syslog],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    syslog_file: str,
) -> None:
    """Check system logs for error messages"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_syslogs link_flaps: cluster: {cluster}, node: {node}, type: {type}"
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
        obj = SyslogImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.LINK_FLAP.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.LINK_FLAP, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_link_flap():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.LINK_FLAP.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            link_flap_output: ShellCommandOut = obj.get_link_flap_report(
                Path(syslog_file), timeout, logger
            )
        except Exception as e:
            link_flap_output = handle_subprocess_exception(e)

        exit_code, msg = process_link_flap_output(
            link_flap_output.stdout,
            link_flap_output.returncode,
        )
        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)


@check_syslogs.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def xid(
    obj: Optional[Syslog],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
) -> None:
    """Check dmesg for Xid errors"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(f"check_syslogs xid: cluster: {cluster}, node: {node}, type: {type}")
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
        obj = SyslogImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.XID_ERRORS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.XID_ERRORS, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_xid_errors():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.XID_ERRORS.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            xid_output: PipedShellCommandOut = obj.get_xid_report(timeout, logger)
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            xid_output = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_xid_output(
            xid_output.stdout,
            xid_output.returncode[0],
        )
        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)


@check_syslogs.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def io_errors(
    obj: Optional[Syslog],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
) -> None:
    """Check dmesg for IO errors"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(
        f"check_syslogs io-errors: cluster: {cluster}, node: {node}, type: {type}"
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
        obj = SyslogImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.IO_ERRORS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.IO_ERRORS, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_io_errors():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.IO_ERRORS.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            io_error_output: PipedShellCommandOut = obj.get_io_error_report(
                timeout, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            io_error_output = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_io_errors_output(
            io_error_output.stdout,
            io_error_output.returncode[0],
        )
        logger.info(f"exit code {exit_code}: {msg}")

    sys.exit(exit_code.value)
