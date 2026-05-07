# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import textwrap
from typing import Callable, Collection, Optional, Tuple

import click
from gcm.exporters import registry
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
)
from gcm.health_checks.types import CHECK_TYPE, ExitCode, LOG_LEVEL

from gcm.monitoring.click import (
    get_docs_for_references,
    heterogeneous_cluster_v1_option,
)
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.monitoring.sink.utils import format_factory_docstrings, get_factory_metadata
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

FnGetZombies = Callable[[int, logging.Logger], PipedShellCommandOut]


def default_get_zombie_procs(
    timeout_secs: int, logger: logging.Logger
) -> PipedShellCommandOut:
    """Invoke ps command to get list of zombie processes in the desired format."""
    cmd = ["ps -eo 'state,pid,user:14,command,etimes'", "awk '/^Z/ { print  }'"]
    logger.info(f"Running command {' | '.join(cmd)}")
    return piped_shell_command(cmd, timeout_secs)


def process_zombie_procs(
    output: str, error_code: int, elapsed_time: int
) -> Tuple[ExitCode, str]:

    if error_code > 0:
        return ExitCode.WARN, "Zombie command failed to execute. output: {output}"

    lines = output.split("\n")
    zombie_count = 0

    for line in lines:
        fields = line.split()
        if len(fields) < 5:
            continue
        try:
            etime = int(fields[len(fields) - 1])
        except Exception:
            return (
                ExitCode.WARN,
                f"Output does not have the expected format. output: {output}",
            )
        if etime > elapsed_time:
            zombie_count += 1

    if zombie_count > 0:
        return ExitCode.WARN, "Found zombie processes. Node needs a reboot."
    else:
        return ExitCode.OK, "No zombie processes were found."


@click.command(
    epilog="\b\nSink documentation:\n\n\b\n"
    + textwrap.indent(
        format_factory_docstrings(get_factory_metadata(registry)),
        prefix=" " * 2,
        predicate=lambda _: True,
    )
    + get_docs_for_references(
        [
            "https://omegaconf.readthedocs.io/en/2.2_branch/usage.html#from-a-dot-list",
        ]
    ),
)
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--elapsed",
    type=int,
    default=300,
    help="Time in seconds for which a zombie process must have run for the check to fail.",
)
@click.pass_obj
@typechecked
def check_zombie(
    obj: Optional[FnGetZombies],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    elapsed: int,
) -> None:
    """Check to make sure no zombie processes are running on the system."""
    get_zombie_procs: FnGetZombies = default_get_zombie_procs if obj is None else obj

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_ZOMBIE,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_zombie(),
    ) as rt:
        try:
            ps_zombie_out = get_zombie_procs(timeout, rt.logger)
        except Exception as e:
            ps_zombie_exception = handle_subprocess_exception(e)
            rt.logger.error(ps_zombie_exception.stdout)
            rt.finish(ExitCode.WARN, ps_zombie_exception.stdout)

        exit_code, msg = process_zombie_procs(
            ps_zombie_out.stdout, ps_zombie_out.returncode[0], elapsed
        )
        rt.finish(exit_code, msg)
