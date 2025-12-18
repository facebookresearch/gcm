# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import re
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Collection, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
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
def check_ipmitool() -> None:
    """ipmitool based checks. i.e. sel"""


class IpmitoolCheck(CheckEnv, Protocol):
    def get_sel(
        self,
        timeout_secs: int,
        use_ipmitool: bool,
        use_sudo: bool,
        logger: logging.Logger,
    ) -> ShellCommandOut: ...

    def clear_sel(
        self, timeout_secs: int, output: str, clear_log_threshold: int
    ) -> None: ...


@dataclass
class IpmitoolCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_sel(
        self,
        timeout_secs: int,
        use_ipmitool: bool,
        use_sudo: bool,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        """Invoke ipmitool/nvipmitool sel command to get the System Event Logs"""
        cmd = ""
        if use_sudo:
            cmd += "sudo "
        if use_ipmitool:
            cmd += "ipmitool sel list"
        else:
            cmd = "nvipmitool sel list"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def clear_sel(
        self, timeout_secs: int, output: str, clear_log_threshold: int
    ) -> None:
        lines = output.splitlines()
        if len(lines) > clear_log_threshold:
            # We can always use the ipmitool for clearing. It is used like that across all cluster.
            shell_command("ipmitool sel clear", timeout_secs)


def process_sel_out(
    output: str,
    error_code: int,
) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"ipmitool sel command FAILED to execute. error_code: {error_code} output: {output}\n",
        )

    sel_errors = [
        re.compile(r"(.*)Power Supply(.*)AC lost(.*)$"),
        re.compile(r"(.*)NVIDIA_MCA_Error(.*)$"),
        re.compile(r"(.*)Uncorrectable error(.*)$"),
        re.compile(r"(.*)Critical Interrupt(.*)Bus Fatal Error(.*)$"),
        re.compile(r"(.*)Critical Interrupt(.*)PCI SERR(.*)$"),
        re.compile(r"(.*)Processor(.*)Throttled(.*)$"),
        re.compile(r"(.*)System Firmwares(.*)BIOS corruption detected(.*)$"),
    ]
    exit_code = ExitCode.OK
    msg = ""
    lines = output.splitlines()
    for line in lines:
        if "Asserted" not in line:
            continue
        for error in sel_errors:
            if re.match(error, line) is not None:
                exit_code = ExitCode.CRITICAL
                try:
                    # split into: line number, date, time, message, status, assertion status
                    msg_alerts = line.split("|")
                    alerts = msg_alerts[3].strip() + ", " + msg_alerts[4].strip()
                    msg += f"Detected error: {alerts}"
                except Exception:
                    msg += f"Invalid output detected: {line}"

    if exit_code == ExitCode.OK:
        msg = "sel reported no errors."

    return exit_code, msg


@check_ipmitool.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--clear_log_threshold",
    type=click.INT,
    default=40,
    help="Number of log lines before clearing the log",
)
@click.option(
    "--ipmitool/--nvipmitool",
    default=True,
    help="Select to execute ipmitool or nvpmitool",
    show_default=True,
)
@click.option(
    "--sudo/--no-sudo",
    default=True,
    help="Select to execute with sudo or without sudo",
    show_default=True,
)
@click.pass_obj
@typechecked
def check_sel(
    obj: Optional[IpmitoolCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    clear_log_threshold: int,
    ipmitool: bool,
    sudo: bool,
) -> None:
    """Check the System Event Log (SEL) with ipmitool/nvipmitool"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-ipmitool check-sel: cluster: {cluster}, node: {node}, type: {type}, log_refresh_threshold: {clear_log_threshold}, use ipmitool: {ipmitool}."
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
        obj = IpmitoolCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.IPMI_SEL.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.IPMI_SEL, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_ipmi_sel():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.IPMI_SEL.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            sel_out: ShellCommandOut = obj.get_sel(timeout, ipmitool, sudo, logger)
        except Exception as e:
            sel_out = handle_subprocess_exception(e)

        exit_code, msg = process_sel_out(sel_out.stdout, sel_out.returncode)

        try:
            obj.clear_sel(timeout, sel_out.stdout, clear_log_threshold)
        except Exception as e:
            msg += f"Clearing sel failed, exception: {e}"
            if ExitCode.WARN > exit_code:
                exit_code = ExitCode.WARN

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
