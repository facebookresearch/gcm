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
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.utils.monitor import init_logger
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked


class DStateProcessCheck(Protocol):
    def get_dstate_procs(
        self, elapsed: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_strace_of_proc(
        self, pid: str, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut: ...


@dataclass
class DStateProcessCheckImpl:
    def get_dstate_procs(
        self, elapsed: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f"comm -1 -2 <(pgrep -r D -l . | sort) <(pgrep --older {elapsed} -l . | sort)"
        logger.info(f"Running command {cmd}")
        return shell_command(cmd, timeout_secs)

    def get_strace_of_proc(
        self, pid: str, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        cmd = f"sudo timeout 0.5 strace -p {pid}"
        logger.info(f"Running command {cmd}")
        return shell_command(cmd, timeout_secs)


def check_dstate_processes(
    obj: DStateProcessCheck,
    elapsed: int,
    process_names: Tuple[str, ...],
    timeout_secs: int,
    logger: logging.Logger,
) -> Tuple[ExitCode, str]:
    # Get all processes older than `elapsed` time ...
    dstate_procs_ret = obj.get_dstate_procs(
        elapsed, timeout_secs=timeout_secs, logger=logger
    )
    dstate_procs_ret.check_returncode()

    process_stuck_in_dstate = []
    # ... then filter out processes which are seemingly not stuck
    for pid, process_name in [
        line.split() for line in dstate_procs_ret.stdout.splitlines()
    ]:
        # If process name filter provided, one must match
        if process_names and not any(re.search(n, process_name) for n in process_names):
            continue

        pid_ret = obj.get_strace_of_proc(pid, timeout_secs=timeout_secs, logger=logger)
        # Cannot attach to process ... or single stuck line
        stderr = pid_ret.stderr or ""
        if pid_ret.returncode == 1 or len(stderr.splitlines()) == 1:
            process_stuck_in_dstate.append(pid)

    return (
        ExitCode.CRITICAL if any(process_stuck_in_dstate) else ExitCode.OK
    ), f"stuck processes: {process_stuck_in_dstate}"


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--elapsed",
    type=int,
    default=300,
    help="Time in seconds for which a dstate process must have run for the check to fail",
)
@click.option(
    "--process-name",
    type=click.STRING,
    required=False,
    multiple=True,
    help="If provided, only consider the given process names; regex allowed",
)
@click.pass_obj
@typechecked
def check_dstate(
    obj: Optional[DStateProcessCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    elapsed: int,
    heterogeneous_cluster_v1: bool,
    process_name: Tuple[str, ...],
) -> None:
    """Check to make sure no dstate processes are running on the system."""
    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-process check-dstate: cluster: {cluster}, node: {node}, type: {type}, process_name: {process_name}"
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
        obj = DStateProcessCheckImpl()

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
                name=HealthCheckName.CHECK_DSTATE.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.CHECK_DSTATE,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_check_dstate():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.CHECK_DSTATE.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        try:
            exit_code, msg = check_dstate_processes(
                obj,
                elapsed=elapsed,
                process_names=process_name,
                timeout_secs=timeout,
                logger=logger,
            )
        except Exception as e:
            ps_dstate_exception = handle_subprocess_exception(e)
            msg = ps_dstate_exception.stdout
            logger.error(msg, e)
            exit_code = ExitCode.WARN
            sys.exit(exit_code.value)

        logger.info(f"exit code {exit_code}: {msg}")
        sys.exit(exit_code.value)
