# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
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
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service ssh-connection: cluster: {cluster}, node: {node}, type: {type}, hostaddress: {hostaddress}."
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
        obj = SSHServiceCheckImpl(cluster, type, log_level, log_folder)

    overall_exit_code = ExitCode.UNKNOWN
    overall_msg = ""
    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.CHECK_SSH.value,
                node=node,
                get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_SSH,
                lambda: (overall_exit_code, overall_msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_ssh():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.CHECK_SSH.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)

        for addr in hostaddress:
            try:
                ssh_conn_out: ShellCommandOut = obj.try_ssh_connection(
                    timeout, addr, logger
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

        logger.info(f"exit code {overall_exit_code}: {overall_msg}")

        sys.exit(overall_exit_code.value)
