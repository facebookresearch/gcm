# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import socket
import sys
from contextlib import ExitStack
from typing import Callable, Collection, Optional, Tuple

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
)
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option

from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

FnGetRunningProcess = Callable[[int, str, logging.Logger], PipedShellCommandOut]


def default_check_running_process(
    timeout_secs: int, process: str, logger: logging.Logger
) -> PipedShellCommandOut:
    """Invoke ps command to check if the process is running."""
    logger.info(
        f"Running command 'ps -ef | grep {process} | grep -v grep | grep -v check-running-process'"
    )
    return piped_shell_command(
        [
            "ps -ef",
            f"grep {process}",
            "grep -v grep",
            "grep -v check-running-process",
        ],
        timeout_secs,
    )


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--process-name",
    "-p",
    type=click.STRING,
    help="The process name to check that is running. Multiple processes can be given.",
    multiple=True,
    required=True,
)
@click.pass_obj
@typechecked
def check_running_process(
    obj: Optional[FnGetRunningProcess],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    process_name: Tuple[str, ...],
    heterogeneous_cluster_v1: bool,
) -> None:
    """Check that the specified processes are running."""
    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-process check-running-process: cluster: {cluster}, node: {node}, type: {type}, process: {process_name}"
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

    check_running_process: FnGetRunningProcess = (
        default_check_running_process if obj is None else obj
    )
    overall_exit_code = ExitCode.UNKNOWN
    overall_msg = ""

    with ExitStack() as s:
        s.enter_context(
            TelemetryContext(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                type=type,
                name=HealthCheckName.RUNNING_PROCESS.value,
                node=node,
                get_exit_code_msg=lambda: (overall_exit_code, overall_msg),
                gpu_node_id=gpu_node_id,
                derived_cluster=derived_cluster,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.RUNNING_PROCESS,
                lambda: (overall_exit_code, overall_msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_running_process():
            overall_exit_code = ExitCode.OK
            overall_msg = (
                f"{HealthCheckName.RUNNING_PROCESS.value} is disabled by killswitch."
            )
            logger.info(overall_msg)
            sys.exit(overall_exit_code.value)

        for proc in process_name:
            try:
                proc_out: PipedShellCommandOut = check_running_process(
                    timeout, proc, logger
                )
            except Exception as e:
                exc_out = handle_subprocess_exception(e)
                proc_out = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

            if proc_out.returncode[0] != 0:
                exit_code = ExitCode.WARN
                msg = f"Command failed. error_code: {proc_out.returncode[0]}, output:\n{proc_out.stdout}"
            else:
                if len(proc_out.stdout) == 0:
                    exit_code = ExitCode.CRITICAL
                    msg = "not running."
                else:
                    exit_code = ExitCode.OK
                    msg = f"running. output:\n {proc_out.stdout}"

            overall_msg += f"Process {proc}: {msg}"
            if exit_code > overall_exit_code:
                overall_exit_code = exit_code

        logger.info(f"exit code {overall_exit_code}: {overall_msg}")

        sys.exit(overall_exit_code.value)
