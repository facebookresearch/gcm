# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import os
import re
import socket
import sys
from contextlib import ExitStack
from typing import Callable, Collection, Optional

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

    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(f"check_hca: cluster: {cluster}, node: {node}, type: {type}")
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

    cmd_str = "ibv_devinfo -l"

    runner = obj
    if runner is None:
        runner = shell_command

    logger.info(f"Running command '{cmd_str}'")

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
                name=HealthCheckName.HCA_COUNT.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.HCA_COUNT, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_hca_count():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.HCA_COUNT.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            output: ShellCommandOut = runner(cmd_str, timeout)
        except Exception as e:
            output = handle_subprocess_exception(e)
            msg = output.stdout
            exit_code = ExitCode.WARN
            logger.error(msg)
            sys.exit(exit_code.value)

        if output.returncode > 0:
            exit_code = ExitCode.WARN
            msg = f"Exit Code {exit_code}: Failed to run command."
            logger.info(msg)
            sys.exit(exit_code.value)

        logger.info(f"Output:\n{output.stdout}")

        lines = output.stdout.split("\n")
        if len(lines) < 1:
            exit_code = ExitCode.CRITICAL
            msg = f"Exit Code {exit_code}: No output detected"
            logger.info(msg)
            sys.exit(exit_code.value)

        match = re.search(r"(\d+) HCAs? found", lines[0])
        if match is None:
            exit_code = ExitCode.CRITICAL
            msg = f"Exit Code {exit_code}: No HCA found"
            logger.info(msg)
            sys.exit(exit_code.value)

        hca_found_count = int(match.group(1))
        if hca_found_count < expected_count:
            exit_code = ExitCode.CRITICAL
            msg = f"Exit Code {exit_code}: Node {node} reports {hca_found_count} HCAs found, but expected {expected_count}"
            logger.info(msg)
            sys.exit(exit_code.value)

        if hca_found_count > expected_count:
            exit_code = ExitCode.WARN
            msg = f"Exit Code {exit_code}: Node {node} reports {hca_found_count} HCAs found, but expected {expected_count}"
            logger.info(msg)
            sys.exit(exit_code.value)

        if exit_code == ExitCode.UNKNOWN:
            exit_code = ExitCode.OK

        msg = (
            f"Exit Code {exit_code}: Node {node} reports {hca_found_count} HCAs found."
        )
        logger.info(msg)
        sys.exit(exit_code.value)
