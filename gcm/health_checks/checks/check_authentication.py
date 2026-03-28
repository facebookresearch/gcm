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
def check_authentication() -> None:
    """authentication based checks. i.e. password check, credentials"""


class AuthenticationCheck(CheckEnv, Protocol):
    def get_pass_status(
        self, timeout_secs: int, user: str, sudo: bool, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def check_file_readable_by_user(
        self, timeout_secs: int, path: str, user: str, op: str, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class AuthenticationCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_pass_status(
        self, timeout_secs: int, user: str, sudo: bool, logger: logging.Logger
    ) -> PipedShellCommandOut:
        cmd = []
        if sudo:
            cmd.append(f"sudo passwd -S {user}")
        else:
            cmd.append(f"passwd -S {user}")
        cmd.append("awk '{ print $2 }'")
        logger.info(f"Running command {' | '.join(cmd)}")
        return piped_shell_command(cmd, timeout_secs)

    def check_file_readable_by_user(
        self, timeout_secs: int, path: str, user: str, op: str, logger: logging.Logger
    ) -> ShellCommandOut:
        op_short = {
            "write": "w",
            "read": "r",
        }[op]

        cmd = f"sudo -u {user} /usr/bin/test -{op_short} {path}"
        logger.info("Running command %s", cmd)
        return shell_command(cmd, timeout_secs)


def process_pass_status(
    output: str, error_code: int, expected_state: str
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"passwd command FAILED to execute. error_code: {error_code} output: {output}\n",
        )

    if output.strip() == expected_state:
        return ExitCode.OK, f"Password status as expected: {expected_state}"
    else:
        return (
            ExitCode.CRITICAL,
            f"Password status {output.strip()} not as expected, {expected_state}",
        )


def process_path_access_status(return_code: int, path: str) -> Tuple[ExitCode, str]:
    if return_code == 0:
        return ExitCode.OK, f"User has access to path: {path}"
    else:
        return (
            ExitCode.CRITICAL,
            f"User does not have access to path: {path}",
        )


@check_authentication.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--user",
    "-u",
    type=click.STRING,
    help="The user to check password status",
    default="root",
)
@click.option(
    "--status",
    "-s",
    type=click.STRING,
    help="The expected password status",
    default="PS",
)
@click.option(
    "--sudo/--no-sudo",
    default=True,
    help="Select to execute with sudo or without sudo",
    show_default=True,
)
@click.pass_obj
@typechecked
def password_status(
    obj: Optional[AuthenticationCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    user: str,
    status: str,
    sudo: bool,
) -> None:
    """Check the password status of a user"""

    if obj is None:
        obj = AuthenticationCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_PASS_STATUS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_pass_status(),
    ) as rt:
        try:
            pass_out: PipedShellCommandOut = obj.get_pass_status(
                timeout, user, sudo, rt.logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            pass_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_pass_status(
            pass_out.stdout, pass_out.returncode[0], status
        )

        rt.finish(exit_code, msg)


@check_authentication.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--user",
    "-u",
    type=click.STRING,
    help="The user to check access against",
    default="root",
)
@click.option(
    "--path",
    "-p",
    type=click.STRING,
    help="The path to check",
)
@click.option(
    "--operation",
    "-o",
    type=click.Choice(["read", "write"]),
    help="Operation to check for access",
    default="write",
)
@click.pass_obj
@typechecked
def check_path_access_by_user(
    obj: Optional[AuthenticationCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    user: str,
    path: str,
    operation: str,
) -> None:
    """Check if a path is accessible by a user"""

    if obj is None:
        obj = AuthenticationCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_PATH_ACCESS,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_user_access_path_check(),
    ) as rt:
        try:
            out = obj.check_file_readable_by_user(
                timeout_secs=timeout,
                user=user,
                path=path,
                op=operation,
                logger=rt.logger,
            )
        except Exception as e:
            out = handle_subprocess_exception(e)

        exit_code, msg = process_path_access_status(
            return_code=out.returncode, path=path
        )

        rt.finish(exit_code, msg)
