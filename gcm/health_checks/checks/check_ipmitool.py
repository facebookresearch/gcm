# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import re
from dataclasses import dataclass
from typing import Collection, Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
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

    if obj is None:
        obj = IpmitoolCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.IPMI_SEL,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_ipmi_sel(),
    ) as rt:
        try:
            sel_out: ShellCommandOut = obj.get_sel(timeout, ipmitool, sudo, rt.logger)
        except Exception as e:
            sel_out = handle_subprocess_exception(e)

        exit_code, msg = process_sel_out(sel_out.stdout, sel_out.returncode)

        try:
            obj.clear_sel(timeout, sel_out.stdout, clear_log_threshold)
        except Exception as e:
            msg += f"Clearing sel failed, exception: {e}"
            if ExitCode.WARN > exit_code:
                exit_code = ExitCode.WARN

        rt.finish(exit_code, msg)
