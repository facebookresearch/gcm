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
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
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
    if obj is None:
        obj = DStateProcessCheckImpl()

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_DSTATE,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_dstate(),
    ) as rt:
        try:
            exit_code, msg = check_dstate_processes(
                obj,
                elapsed=elapsed,
                process_names=process_name,
                timeout_secs=timeout,
                logger=rt.logger,
            )
        except Exception as e:
            ps_dstate_exception = handle_subprocess_exception(e)
            msg = ps_dstate_exception.stdout
            rt.logger.error(msg, e)
            exit_code = ExitCode.WARN

        rt.finish(exit_code, msg)
