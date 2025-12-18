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


class SlurmServiceCheck(CheckEnv, Protocol):
    def get_slurmctld_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...

    def get_node_state(
        self, timeout_secs: int, node: str, logger: logging.Logger
    ) -> ShellCommandOut: ...

    def get_cluster_node_state(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut: ...


@dataclass
class SlurmServiceCheckImpl:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_slurmctld_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        """Call scontrol to see how many slurmctld daemon controllers the node can contact.
        Returns two exit codes: one for 'scontrol ping' and a second for the 'grep -c'
        """

        logger.info("Running command 'scontrol ping | grep -c 'UP''")
        return piped_shell_command(["scontrol ping", "grep -c 'UP'"], timeout_secs)

    def get_node_state(
        self, timeout_secs: int, node: str, logger: logging.Logger
    ) -> ShellCommandOut:
        """Get the state of the node as reported by Slurm"""
        if self.cluster in ["rsc", "ava", "sbx"]:
            node = node.split(".")[0]
        cmd = f"sinfo -n {node} -o %T -h"
        logger.info(f"Running command '{cmd}'")
        return shell_command(cmd, timeout_secs)

    def get_cluster_node_state(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        """Call scontrol to see the state of the nodes in the cluster.
        Returns five exit codes: one for 'scontrol show node', one for awk, one for sed, one for sor, and one for uniq.
        """
        logger.info(
            "Running command 'scontrol show node | awk '/State=/ {gsub(/State=/,"
            "); print $1}' | sed -e 's/*//g' | sort | uniq -c'"
        )
        return piped_shell_command(
            [
                "scontrol show node",
                "awk '/State=/ {gsub(/State=/,\" \"); print $1}'",
                "sed -e 's/*//g'",
                "sort",
                "uniq -c",
            ],
            timeout_secs,
        )


def process_slurmctld_count_output(
    output: str, error_code: int, expected_count: int
) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"scontrol ping command failed to execute. error_code: {error_code}, output: {output}",
        )
    else:
        try:
            slurmctld_count_found = int(output)
        except Exception:
            return (
                ExitCode.WARN,
                f"scontrol ping command invalid output. output: {output}",
            )

    if slurmctld_count_found < expected_count:
        return (
            ExitCode.CRITICAL,
            f"Insufficient slurmctld daemon count. Expected at least: {expected_count} and found: {slurmctld_count_found}",
        )
    else:
        return (
            ExitCode.OK,
            f"Sufficient slurmctld daemon count. Expected at least: {expected_count} and found: {slurmctld_count_found}",
        )


def process_node_state(output: str, error_code: int) -> Tuple[ExitCode, str]:
    critical_node_states = [
        "down",
        "drained",
        "draining",
        "fail",
        "failing",
        "maint",
        "unknown",
    ]

    good_node_states = [
        "allocated",
        "completing",
        "idle",
        "mixed",
        "planned",
        "reserved",
    ]

    if error_code > 0:
        return (
            ExitCode.WARN,
            f"sinfo -n command failed to execute. error_code: {error_code}, output: {output}",
        )
    else:
        node_state = output.strip()
        if any(state in node_state for state in critical_node_states):
            return (
                ExitCode.WARN,
                f"node is in bad state: {node_state}, and cannot accept jobs.",
            )
        elif any(state in node_state for state in good_node_states):
            return (
                ExitCode.OK,
                f"node is in good state: {node_state}, and can accept jobs.",
            )
        else:
            return (
                ExitCode.WARN,
                f"node is in undefined state: {node_state}.",
            )


def process_cluster_state(
    output: str,
    error_code: int,
    critical_thr: int,
    warning_thr: int,
) -> Tuple[ExitCode, str]:
    if error_code > 0:
        return (
            ExitCode.WARN,
            f"scontrol show node command failed to execute. error_code: {error_code}, output: {output}",
        )

    total_state_cnt = 0
    bad_state_cnt = 0

    for line in output.splitlines():
        line_info = line.split()
        try:
            state_cnt = int(line_info[0])
            total_state_cnt += state_cnt
            if "DOWN" in line or "DRAIN" in line:
                bad_state_cnt += state_cnt
        except Exception:
            return (
                ExitCode.WARN,
                f"scontrol show node command returned invalid output. output: {output}",
            )

    bad_state_fraction = bad_state_cnt / total_state_cnt * 100

    if bad_state_fraction > critical_thr:
        return (
            ExitCode.CRITICAL,
            f"{bad_state_cnt} / {total_state_cnt} = {bad_state_fraction}% of nodes are in bad slurm state. Critical threshold is {critical_thr}%.",
        )
    elif bad_state_fraction > warning_thr:
        return (
            ExitCode.WARN,
            f"{bad_state_cnt} / {total_state_cnt} = {bad_state_fraction}% of nodes are in bad slurm state. Warning threshold is {warning_thr}%.",
        )

    return (
        ExitCode.OK,
        f"Nodes in bad state are below the critial and warning thresholds of {critical_thr}% and {warning_thr}% respectively.",
    )


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--slurmctld-count",
    type=click.INT,
    help="Minimum number of slurmctld daemons that should be present. (primary, primary and secondary)",
    required=True,
)
@click.pass_obj
@typechecked
def slurmctld_count(
    obj: Optional[SlurmServiceCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    slurmctld_count: int,
) -> None:
    """Checks how many slurmctld controller daemons are reachable. It needs to contact at least as many as the user requests."""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service slurmctld_count: cluster: {cluster}, node: {node}, type: {type}, slurmctld-count: {slurmctld_count}."
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
        obj = SlurmServiceCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.SLURMCTLD_COUNT.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.SLURMCTLD_COUNT,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_slrmctld_count():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.SLURMCTLD_COUNT.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            slrm_control_out: PipedShellCommandOut = obj.get_slurmctld_count(
                timeout, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            slrm_control_out = PipedShellCommandOut(
                [exc_out.returncode], exc_out.stdout
            )

        exit_code, msg = process_slurmctld_count_output(
            slrm_control_out.stdout,
            slrm_control_out.returncode[0],
            slurmctld_count,
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.pass_obj
@typechecked
def node_slurm_state(
    obj: Optional[SlurmServiceCheck],
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
    """Checks the status of the node to determine whether it can accept jobs or not"""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service node_slurm_status: cluster: {cluster}, node: {node}, type: {type}."
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
        obj = SlurmServiceCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.SLURM_STATE.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.SLURM_STATE, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_slurm_state():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.SLURM_STATE.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            node_state_out: ShellCommandOut = obj.get_node_state(timeout, node, logger)
        except Exception as e:
            node_state_out = handle_subprocess_exception(e)

        exit_code, msg = process_node_state(
            node_state_out.stdout, node_state_out.returncode
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--critical_threshold",
    type=click.IntRange(0, 100),
    default=25,
    help="Percentage (%) of unavailable nodes for Critical",
)
@click.option(
    "--warning_threshold",
    type=click.IntRange(0, 100),
    default=15,
    help="Percentage (%) of unavailable nodes for Warning",
)
@click.pass_obj
@typechecked
def cluster_availability(
    obj: Optional[SlurmServiceCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    critical_threshold: int,
    warning_threshold: int,
) -> None:
    """Checks the if the percentage of DRAIN and DOWN nodes is above the defined threshold"""
    node: str = socket.gethostname()
    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )
    logger.info(
        f"check-service cluster_availability: cluster: {cluster}, node: {node}, type: {type}, critical_threshold: {critical_threshold}, warning_threshold: {warning_threshold}"
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
        obj = SlurmServiceCheckImpl(cluster, type, log_level, log_folder)

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
                name=HealthCheckName.SLURM_CLUSTER_AVAIL.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
            )
        )
        s.enter_context(
            OutputContext(
                type,
                HealthCheckName.SLURM_CLUSTER_AVAIL,
                lambda: (exit_code, msg),
                verbose_out,
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_slurm_cluster_avail():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.SLURM_CLUSTER_AVAIL.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)
        try:
            cluster_state: PipedShellCommandOut = obj.get_cluster_node_state(
                timeout, logger
            )
        except Exception as e:
            exc_out = handle_subprocess_exception(e)
            cluster_state = PipedShellCommandOut([exc_out.returncode], exc_out.stdout)

        exit_code, msg = process_cluster_state(
            cluster_state.stdout,
            cluster_state.returncode[0],
            critical_threshold,
            warning_threshold,
        )

        logger.info(f"exit code {exit_code}: {msg}")

        sys.exit(exit_code.value)
