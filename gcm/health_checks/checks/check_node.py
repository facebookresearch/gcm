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
def check_node() -> None:
    """various node based checks. i.e. uptime, dnf repo"""


class NodeCheck(CheckEnv, Protocol):
    def get_uptime(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_module(
        self, timeout_secs: int, module: str, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_dnf_repos(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class NodeCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_uptime(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        cmd = ["cat /proc/uptime", "awk -F. '{ print $1 }'"]
        logger.info(f"Running command: {' | '.join(cmd)}")
        return piped_shell_command(cmd, timeout_secs)

    def get_module(
        self, timeout_secs: int, module: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        cmd = ["lsmod", f"grep {module}", "wc -l"]
        logger.info(f"Running command: {' | '.join(cmd)}")
        return piped_shell_command(cmd, timeout_secs)

    def get_dnf_repos(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = "dnf repolist -v --refresh"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)


def process_uptime(
    output: str, error_code: int, uptime_threshold: int
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.WARN,
            f"cat /proc/uptime command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    try:
        uptime_secs = int(output)
    except ValueError:
        return ExitCode.WARN, f"Invalid output returned: {output}"

    if uptime_secs > uptime_threshold:
        return ExitCode.OK, f"Node is up enough time: {uptime_secs} secs"
    else:
        return ExitCode.WARN, f"Node recently booted. It's up for: {uptime_secs} secs"


@check_node.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--uptime-threshold",
    type=click.IntRange(min=0),
    default=600,
    help="Threshold in secs before warning the node recently booted.",
)
@click.pass_obj
@typechecked
def uptime(
    obj: Optional[NodeCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    uptime_threshold: int,
) -> None:
    """Check if the node recently booted"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-node uptime: cluster: {cluster}, node: {node}, type: {type}, uptime-threshold: {uptime_threshold}."
    )
    try:
        gpu_node_id = gni_lib.get_gpu_node_id()
    except Exception as e:
        gpu_node_id = None
        logger.warning(f"Could not get gpu_node_id, likely not a GPU host: {e}")
    if obj is None:
        obj = NodeCheckImpl(cluster, type, log_level, log_folder)

    derived_cluster = get_derived_cluster(
        cluster=cluster,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        data={"Node": node},
    )

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
                name=HealthCheckName.CHECK_UPTIME.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_UPTIME,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_uptime():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_UPTIME.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            uptime_out: PipedShellCommandOut = obj.get_uptime(timeout, logger)
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            uptime_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_uptime(
            uptime_out.stdout, uptime_out.returncode[0], uptime_threshold
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


def process_module(
    output: str, error_code: int, mod_count: int
) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"lsmod command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    try:
        appearences = int(output)
    except ValueError:
        return ExitCode.WARN, f"Invalid output returned: {output}"

    if appearences >= mod_count:
        return (
            ExitCode.OK,
            f"Module appears enough times {appearences} >= {mod_count} threshold",
        )
    else:
        return (
            ExitCode.CRITICAL,
            f"Module doesn't appear enough times {appearences} < {mod_count} threshold",
        )


@check_node.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--module",
    "-m",
    type=click.STRING,
    multiple=True,
    required=True,
    help="The module to check",
)
@click.option(
    "--mod_count",
    type=click.IntRange(min=0),
    multiple=True,
    default=[1],
    show_default=True,
    help="The number of times that it appears on lsmod",
)
@click.pass_obj
@typechecked
def check_module(
    obj: Optional[NodeCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    module: Tuple[str, ...],
    mod_count: Tuple[int, ...],
) -> None:
    """Check if the node recently booted"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-node check-module: cluster: {cluster}, node: {node}, type: {type}, module: {module}, mod_count: {mod_count}."
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

    if len(mod_count) != len(module):
        raise ValueError("Number of modules and mod_counts must be equal.")

    if obj is None:
        obj = NodeCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_MODULE.value,
                node=node,
                get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_MODULE,
                lambda: (overall_exit_code, overall_msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_uptime():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.CHECK_MODULE.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)
        for m, m_count in zip(module, mod_count):
            try:
                module_out: PipedShellCommandOut = obj.get_module(timeout, m, logger)
            except Exception as e:
                exc_out = handle_subprocess_exception(e)
                module_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

            exit_code, msg = process_module(
                module_out.stdout, module_out.returncode[0], m_count
            )

            overall_msg += f"Module {m}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        logger.info(f"exit code {overall_exit_code}: {overall_msg}")

        sys.exit(overall_exit_code.value)


def process_dnf_repos(
    output: str,
    error_code: int,
) -> Tuple[ExitCode, str]:
    if error_code > 0 or len(output) == 0:
        return (
            ExitCode.CRITICAL,
            f"dnf repos command FAILED to execute. error_code: {error_code} output: {output}\n",
        )
    else:
        return (
            ExitCode.OK,
            "dnf repos are reachable\n",
        )


@check_node.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def check_dnf_repos(
    obj: Optional[NodeCheck],
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
    """Check that the dnf repos are reachable"""

    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-node dnf-repos: cluster: {cluster}, node: {node}, type: {type}."
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
        obj = NodeCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.CHECK_DNF_REPOS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_DNF_REPOS,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_dnf_repos():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_DNF_REPOS.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            dnf_repos_out: ShellCommandOut = obj.get_dnf_repos(timeout, logger)
        except Exception as e:
            dnf_repos_out = handle_subprocess_exception(e)

        exit_code, msg = process_dnf_repos(
            dnf_repos_out.stdout, dnf_repos_out.returncode
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
