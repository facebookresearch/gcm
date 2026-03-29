# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import re
from typing import Callable, Collection, Optional

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

FnShellCommand = Callable[[str, int], ShellCommandOut]


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--expected-count",
    type=int,
    required=True,
    help="Expected count of HCAs in a node",
)
@click.pass_obj
@typechecked
def check_hca(
    obj: Optional[FnShellCommand],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    expected_count: int,
) -> None:
    """
    Check if HCAs are present and count matches the expectation.
    """
    runner = obj
    if runner is None:
        runner = shell_command

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.HCA_COUNT,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_hca_count(),
    ) as rt:
        cmd_str = "ibv_devinfo -l"
        rt.logger.info(f"Running command '{cmd_str}'")

        try:
            output: ShellCommandOut = runner(cmd_str, timeout)
        except Exception as e:
            output = handle_subprocess_exception(e)
            rt.logger.error(output.stdout)
            rt.finish(ExitCode.WARN, output.stdout)

        if output.returncode > 0:
            msg = "Failed to run command."
            rt.finish(ExitCode.WARN, msg)

        rt.logger.info(f"Output:\n{output.stdout}")

        lines = output.stdout.split("\n")
        if len(lines) < 1:
            msg = "No output detected"
            rt.finish(ExitCode.CRITICAL, msg)

        match = re.search(r"(\d+) HCAs? found", lines[0])
        if match is None:
            msg = "No HCA found"
            rt.finish(ExitCode.CRITICAL, msg)

        hca_found_count = int(match.group(1))
        if hca_found_count < expected_count:
            exit_code = ExitCode.CRITICAL
            msg = f"Node {rt.node} reports {hca_found_count} HCAs found, but expected {expected_count}"
            rt.finish(exit_code, msg)

        if hca_found_count > expected_count:
            exit_code = ExitCode.WARN
            msg = f"Node {rt.node} reports {hca_found_count} HCAs found, but expected {expected_count}"
            rt.finish(exit_code, msg)

        exit_code = ExitCode.OK
        msg = f"Node {rt.node} reports {hca_found_count} HCAs found."
        rt.finish(exit_code, msg)
