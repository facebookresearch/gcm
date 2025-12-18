# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Collection, List, Optional, Protocol, Tuple

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContext
from gcm.health_checks.checks.check_slurm import (
    cluster_availability,
    node_slurm_state,
    slurmctld_count,
)
from gcm.health_checks.checks.check_ssh import ssh_connection
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
def check_service() -> None:
    """check the system services. i.e. slurmd, sssd, etc."""


class ServiceCheck(CheckEnv, Protocol):
    def get_service_status(
        self, timeout_secs: int, service: str, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_package_rpm_version(
        self, timeout_secs: int, package_name: str, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class ServiceCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_service_status(
        self, timeout_secs: int, service: str, logger: logging.Logger
    ) -> ShellCommandOut:
        """Invoke the systemctl command to get the status of the slurmd service"""
        cmd = f"systemctl is-active {service}"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_package_rpm_version(
        self, timeout_secs: int, package_name: str, logger: logging.Logger
    ) -> ShellCommandOut:
        """ "Get the version of an installed package"""
        cmd = "rpm -q --qf '%{VERSION}-%{RELEASE}\n' " + package_name
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--service",
    "-s",
    type=click.STRING,
    help="Services to check for status",
    multiple=True,
    required=True,
)
@click.pass_obj
@typechecked
def service_status(
    obj: Optional[ServiceCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    service: Tuple[str, ...],
) -> None:
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service service-status: cluster: {cluster}, node: {node}, type: {type}, services: {service}."
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
        obj = ServiceCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.SERVICE_STATUS.value,
                node=node,
                get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.SERVICE_STATUS,
                lambda: (overall_exit_code, overall_msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_service_status():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.SERVICE_STATUS.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)
        for serv in service:
            try:
                serv_status_out: ShellCommandOut = obj.get_service_status(
                    timeout, serv, logger
                )
            except Exception as e:
                serv_status_out = handle_subprocess_exception(e)

            if serv_status_out.returncode > 0:
                exit_code = ExitCode.CRITICAL
                msg = f"not running. error_code: {serv_status_out.returncode}, output: {serv_status_out.stdout}"
            else:
                exit_code = ExitCode.OK
                msg = f"running. Status: {serv_status_out.stdout}"

            overall_msg += f"Service {serv}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        logger.info(f"exit code {overall_exit_code}: {overall_msg}")

        sys.exit(overall_exit_code.value)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--package",
    "-p",
    type=click.STRING,
    help="Package to check for version",
    required=True,
)
@click.option(
    "--version",
    "-v",
    type=click.STRING,
    help="Version in the format %{VERSION}-%{RELEASE}",
    required=True,
)
@click.pass_obj
@typechecked
def package_version(
    obj: Optional[ServiceCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    package: str,
    version: str,
) -> None:
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service package-version: cluster: {cluster}, node: {node}, type: {type}, package: {package}."
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
        obj = ServiceCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.PACKAGE_VERSION.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.PACKAGE_VERSION,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_service_status():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.PACKAGE_VERSION.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            version_out: ShellCommandOut = obj.get_package_rpm_version(
                timeout, package, logger
            )
        except Exception as e:
            version_out = handle_subprocess_exception(e)

        if version_out.returncode > 0:
            exit_code = ExitCode.WARN
            msg = f"rpm command failed. error_code: {version_out.returncode}, output: {version_out.stdout}"
        else:
            if version_out.stdout.strip() == version.strip():
                exit_code = ExitCode.OK
                msg = f"Version is as expected. version: {version}"
            else:
                exit_code = ExitCode.CRITICAL
                msg = f"Version  missmatch. Expected version: {version} and found version: {version_out.stdout}"

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


list_of_checks: List[click.core.Command] = [
    service_status,
    package_version,
    slurmctld_count,
    node_slurm_state,
    cluster_availability,
    ssh_connection,
]

for check in list_of_checks:
    check_service.add_command(check)

if __name__ == "__main__":
    check_service()
