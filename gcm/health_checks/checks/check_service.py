# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from typing import Collection, List, Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
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
    if obj is None:
        obj = ServiceCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.SERVICE_STATUS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_service_status(),
    ) as rt:
        overall_exit_code = ExitCode.UNKNOWN
        overall_msg = ""
        for serv in service:
            try:
                serv_status_out: ShellCommandOut = obj.get_service_status(
                    timeout, serv, rt.logger
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

        rt.finish(overall_exit_code, overall_msg)


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
    if obj is None:
        obj = ServiceCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.PACKAGE_VERSION,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_service_status(),
    ) as rt:
        try:
            version_out: ShellCommandOut = obj.get_package_rpm_version(
                timeout, package, rt.logger
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

        rt.finish(exit_code, msg)


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
