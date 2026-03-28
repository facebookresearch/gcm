# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
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


class SSHServiceCheck(CheckEnv, Protocol):
    def try_ssh_connection(
        self, timeout_secs: int, hostaddress: str, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class SSHServiceCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def try_ssh_connection(
        self, timeout_secs: int, hostaddress: str, logger: logging.Logger
    ) -> ShellCommandOut:
        """Try to ssh to a hostaddress and then exit"""
        cmd = f"ssh {hostaddress} exit"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--hostaddress",
    "--host",
    type=click.STRING,
    help="Hostaddresses to check for ssh connection",
    required=True,
    multiple=True,
)
@click.pass_obj
@typechecked
def ssh_connection(
    obj: Optional[SSHServiceCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    hostaddress: Tuple[str, ...],
) -> None:
    """Checks how many slurmctld controller daemons are reachable. It needs to contact at least as many as the user requests."""

    if obj is None:
        obj = SSHServiceCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_SSH,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_ssh(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""

        for addr in hostaddress:
            try:
                ssh_conn_out: ShellCommandOut = obj.try_ssh_connection(
                    timeout, addr, rt.logger
                )
            except Exception as e:
                ssh_conn_out = handle_subprocess_exception(e)

            if ssh_conn_out.returncode > 0:
                exit_code = ExitCode.CRITICAL
                msg = f"ssh connection failed. error_code: {ssh_conn_out.returncode}, output: {ssh_conn_out.stdout}\n"
            else:
                exit_code = ExitCode.OK
                msg = "ssh connection succeeded.\n"

            overall_msg += f"Host {addr}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        rt.finish(overall_exit_code, overall_msg)
