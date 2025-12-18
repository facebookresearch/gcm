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

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-authentication password-status: cluster: {cluster}, node: {node}, type: {type}, user: {user} expected status: {status}."
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
        obj = AuthenticationCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_PASS_STATUS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_PASS_STATUS,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_pass_status():
            exit_code = ExitCode.OK
            msg = (
                f"{HealthCheckName.CHECK_PASS_STATUS.value} is disabled by killswitch."
            )
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            pass_out: PipedShellCommandOut = obj.get_pass_status(
                timeout, user, sudo, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            pass_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_pass_status(
            pass_out.stdout, pass_out.returncode[0], status
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


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

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-authentication password-status: cluster: {cluster}, node: {node}, type: {type}, user: {user}, path: {path}, operation: {operation}"
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
        obj = AuthenticationCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_PATH_ACCESS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_PATH_ACCESS,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_user_access_path_check():
            exit_code = ExitCode.OK
            msg = (
                f"{HealthCheckName.CHECK_PATH_ACCESS.value} is disabled by killswitch."
            )
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            out = obj.check_file_readable_by_user(
                timeout_secs=timeout,
                user=user,
                path=path,
                op=operation,
                logger=logger,
            )
        except Exception as e:
            out = handle_subprocess_exception(e)

        exit_code, msg = process_path_access_status(
            return_code=out.returncode, path=path
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
