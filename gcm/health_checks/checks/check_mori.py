# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""MORI (Modular RDMA Interface) health check for AMD GPU nodes.

Validates MORI installation and optionally runs MORI-EP/MORI-IO tests.
Uses pre-installed mori package (smoke) or pre-deployed repo (pytest); GCM does not clone the repo.
Emits CommunicationCheckLog with optional bandwidth/latency metrics when benchmark output is present.
"""

import logging
import os
import re
import socket
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    get_args,
    Literal,
    Optional,
)

import click

import gni_lib
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.check_utils.telem import TelemetryContextCommunication
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

FnShellCommand = Callable[[str, int], ShellCommandOut]

MORI_TEST = Literal["smoke", "dispatch_combine", "io", "both"]

# Smoke: only requires installed mori package; no repo, no torchrun.
MORI_SMOKE_CMD = (
    "python -c \""
    "import mori; "
    "assert hasattr(mori, 'ops'), 'mori.ops missing'; "
    "assert hasattr(mori, 'io'), 'mori.io missing'; "
    "print('MORI smoke OK')\""
)


@dataclass
class MoriTestProcessedOutput:
    message: str
    exitcode: ExitCode
    stdout: Optional[str]


def process_mori_output(output: ShellCommandOut, test_kind: str) -> MoriTestProcessedOutput:
    """Interpret MORI test subprocess result."""
    out_str = (getattr(output, "stdout", None) or "") or ""
    if output.returncode == 0:
        return MoriTestProcessedOutput(
            message=f"MORI Test - {test_kind} - ran successfully",
            exitcode=ExitCode.OK,
            stdout=out_str,
        )
    return MoriTestProcessedOutput(
        message=f"MORI Test - {test_kind} - FAILED to run.",
        exitcode=ExitCode.CRITICAL,
        stdout=out_str,
    )


def parse_mori_metrics_from_stdout(stdout: Optional[str]) -> Dict[str, Any]:
    """
    Parse MORI-EP benchmark stdout for bandwidth and latency (best-effort).
    Looks for "Best Dispatch ... X.XX GB/s, latency=Y us" and similar lines.
    Returns dict with keys: dispatch_bw_gbps, combine_bw_gbps, latency_us (total).
    """
    metrics: Dict[str, Any] = {}
    if not stdout:
        return metrics
    # Best Dispatch  (dtype): X.XX GB/s, latency=Y us
    m_disp = re.search(
        r"Best Dispatch\s+.*?:\s*([\d.]+)\s*GB/s.*?latency[=:]?\s*([\d.]+)\s*us",
        stdout,
        re.IGNORECASE | re.DOTALL,
    )
    if m_disp:
        try:
            metrics["dispatch_bw_gbps"] = float(m_disp.group(1))
            metrics["dispatch_latency_us"] = float(m_disp.group(2))
        except (ValueError, IndexError):
            pass
    # Best Combine   (dtype, ...): X.XX GB/s, latency=Y us
    m_comb = re.search(
        r"Best Combine\s+.*?:\s*([\d.]+)\s*GB/s.*?latency[=:]?\s*([\d.]+)\s*us",
        stdout,
        re.IGNORECASE | re.DOTALL,
    )
    if m_comb:
        try:
            metrics["combine_bw_gbps"] = float(m_comb.group(1))
            metrics["combine_latency_us"] = float(m_comb.group(2))
        except (ValueError, IndexError):
            pass
    # Total Dispatch+Combine latency: Z us
    m_total = re.search(
        r"Total Dispatch\+Combine latency[:\s]+([\d.]+)\s*us",
        stdout,
        re.IGNORECASE,
    )
    if m_total:
        try:
            metrics["latency_us"] = float(m_total.group(1))
        except (ValueError, IndexError):
            pass
    # Single bandwidth for generic field (prefer dispatch if present)
    if "dispatch_bw_gbps" in metrics:
        metrics["bandwidth_gbps"] = metrics["dispatch_bw_gbps"]
    elif "combine_bw_gbps" in metrics:
        metrics["bandwidth_gbps"] = metrics["combine_bw_gbps"]
    # Optional breakdown for extra_metrics (CommunicationCheckLog.extra_metrics)
    extra: Dict[str, float] = {}
    if "dispatch_latency_us" in metrics:
        extra["dispatch_latency_us"] = metrics["dispatch_latency_us"]
    if "combine_latency_us" in metrics:
        extra["combine_latency_us"] = metrics["combine_latency_us"]
    if extra:
        metrics["extra_metrics"] = extra
    return metrics


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--mori-repo",
    type=click.Path(file_okay=False),
    default=None,
    help="Path to pre-deployed MORI repo for full pytest. If omitted, run smoke only using installed mori package.",
)
@click.option(
    "--mori-test",
    type=click.Choice(get_args(MORI_TEST)),
    default="smoke",
    show_default=True,
    help="Test to run: smoke (installed package only), dispatch_combine, io, or both (latter require --mori-repo).",
)
@click.pass_obj
def check_mori(
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
    mori_repo: Optional[str],
    mori_test: MORI_TEST,
) -> None:
    """
    Run MORI (Modular RDMA Interface) check to validate MORI on AMD GPU nodes.

    Default: smoke test using installed mori package (pip install mori). No repo clone.
    Optional: with --mori-repo <path> run full pytest from that pre-deployed path.
    """
    node: str = socket.gethostname()

    logger, _ = init_logger(
        logger_name=type,
        log_dir=os.path.join(log_folder, type + "_logs"),
        log_name=node + ".log",
        log_level=getattr(logging, log_level),
    )

    logger.info(f"check_mori: cluster: {cluster}, node: {node}, type: {type}")
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

    runner = obj
    if runner is None:
        runner = shell_command

    exit_code = ExitCode.UNKNOWN
    msg = ""
    communication_metrics: Dict[str, Any] = {}

    def get_communication_metrics() -> Dict[str, Any]:
        return communication_metrics

    with ExitStack() as s:
        s.enter_context(
            TelemetryContextCommunication(
                sink=sink,
                sink_opts=sink_opts,
                logger=logger,
                cluster=cluster,
                derived_cluster=derived_cluster,
                type=type,
                name=HealthCheckName.MORI_TESTS.value,
                node=node,
                get_exit_code_msg=lambda: (exit_code, msg),
                gpu_node_id=gpu_node_id,
                get_communication_metrics=get_communication_metrics,
            )
        )
        s.enter_context(
            OutputContext(
                type, HealthCheckName.MORI_TESTS, lambda: (exit_code, msg), verbose_out
            )
        )
        ff = FeatureValueHealthChecksFeatures()
        if ff.get_healthchecksfeatures_disable_mori_tests():
            exit_code = ExitCode.OK
            msg = f"{HealthCheckName.MORI_TESTS.value} is disabled by killswitch."
            logger.info(msg)
            sys.exit(exit_code.value)

        if mori_repo and mori_test != "smoke":
            # Full pytest from pre-deployed repo
            repo_path = os.path.abspath(mori_repo.rstrip("/"))
            if not os.path.isdir(repo_path):
                logger.error(f"mori-repo path is not a directory: {repo_path}")
                exit_code = ExitCode.CRITICAL
                msg = f"MORI Test - {mori_test} - mori-repo path not found or not a directory: {repo_path}"
                sys.exit(exit_code.value)
            tests_dir = os.path.join(repo_path, "tests", "python")
            if mori_test == "dispatch_combine":
                test_path = os.path.join(tests_dir, "ops", "test_dispatch_combine.py")
            elif mori_test == "io":
                test_path = os.path.join(tests_dir, "io")
            elif mori_test == "both":
                test_path = tests_dir
            else:
                test_path = tests_dir
            if not os.path.exists(test_path):
                logger.error(f"Test path does not exist: {test_path}")
                exit_code = ExitCode.CRITICAL
                msg = f"MORI Test - {mori_test} - test path not found: {test_path}"
                sys.exit(exit_code.value)
            cmd = f"cd {repo_path} && python -m pytest {test_path} -q --timeout=60"
            logger.info(f"Running pytest: {cmd}")
        else:
            # Smoke: use installed mori only
            cmd = MORI_SMOKE_CMD
            mori_test = "smoke"
            logger.info(f"Running MORI smoke: {cmd}")

        try:
            output: ShellCommandOut = runner(cmd, timeout)
        except Exception as e:
            output = handle_subprocess_exception(e)

        processed = process_mori_output(output, mori_test)
        exit_code = processed.exitcode
        msg = f"Exit Code {exit_code.value}: {processed.message}"
        logger.info(msg)
        logger.info(f"Output:\n{processed.stdout or ''}")
        print(processed.stdout or "")

        # Parse MORI benchmark stdout for telemetry (best-effort)
        parsed = parse_mori_metrics_from_stdout(processed.stdout)
        if parsed:
            communication_metrics.update(parsed)

        sys.exit(exit_code.value)
