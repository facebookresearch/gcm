# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Run Pantheon GPU diagnostics workloads and report what they find.

Pantheon (https://pantheongpu.com) is an open-source GPU diagnostics suite for
NVIDIA and AMD GPUs. Each workload loads one part of the card, verifies its
results for silent data corruption and reads the card's error counters before
and after the run. This check runs the selected workloads on the selected GPUs
and turns Pantheon's report into a health-check result.
"""

import json
import logging
import os
import pathlib
import shlex
import tempfile
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

import click
from gcm.health_checks.check_utils.runtime import HealthCheckRuntime
from gcm.health_checks.click import (
    common_arguments,
    telemetry_argument,
    timeout_argument,
)
from gcm.health_checks.env_variables import EnvCtx
from gcm.health_checks.subprocess import (
    handle_subprocess_exception,
    shell_command,
    ShellCommandOut,
)
from gcm.health_checks.types import CHECK_TYPE, CheckEnv, ExitCode, LOG_LEVEL
from gcm.monitoring.click import heterogeneous_cluster_v1_option
from gcm.monitoring.features.gen.generated_features_healthchecksfeatures import (
    FeatureValueHealthChecksFeatures,
)
from gcm.schemas.health_check.health_check_name import HealthCheckName
from typeguard import typechecked

DEFAULT_WORKLOADS = ("memory_read", "march_test")

# Workloads whose failure means the memory returned wrong data, as opposed to
# a workload that could not run.
DIAGNOSTIC_WORKLOADS = frozenset(
    {
        "march_test",
        "galpat",
        "memory_hammer",
        "memory_retention",
        "memory_retention_bake",
        "ras_validator",
    }
)

GPU_TEMPERATURE_WARN_C = 90.0

# The PCIe link changing power state moves this counter on healthy hardware.
BENIGN_COUNTERS = ("l0_to_recovery",)

# Variables that renumber or hide GPUs. The check names GPUs as the node
# numbers them, so the workloads run with these unset.
DEVICE_VARIABLES = (
    "CUDA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
)


@dataclass
class PantheonRun:
    """What one Pantheon invocation produced."""

    command: ShellCommandOut
    rows: List[Dict[str, Any]] = field(default_factory=list)
    mock: bool = False


class PantheonCheck(CheckEnv, Protocol):
    """Provide a class stub definition."""

    def run_workload(
        self,
        pantheon_bin: Optional[str],
        workload: str,
        devices: List[int],
        duration: int,
        mem_percent: int,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PantheonRun: ...


def read_reports(
    report_dir: pathlib.Path, workload: str
) -> Tuple[List[Dict[str, Any]], bool]:
    """Return the result rows of a workload, one per GPU, and whether Pantheon
    ran on its CPU backend instead of a GPU.

    Pantheon writes a report for the session and a second one for each workload
    that completed, holding the same row, so rows are keyed by GPU.
    """
    rows: Dict[Any, Dict[str, Any]] = {}
    mock = False
    for path in sorted(report_dir.glob("*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(report, dict):
            continue
        for gpu in report.get("gpu_static_info") or []:
            if isinstance(gpu, dict) and str(gpu.get("type", "")).upper() == "MOCK":
                mock = True
        for row in report.get("test_results") or []:
            if isinstance(row, dict) and row.get("Test Name") == workload:
                rows[row.get("GPU ID")] = row
    return [rows[gpu] for gpu in sorted(rows, key=str)], mock


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assess_row(row: Dict[str, Any]) -> Tuple[ExitCode, str]:
    """Turn the result of one workload on one GPU into an exit code."""
    gpu = row.get("GPU ID")
    workload = row.get("Test Name")
    prefix = f"GPU {gpu} {workload}:"

    failed = (
        row.get("Unit") == "ERR"
        or str(row.get("Status") or "PASS").upper() == "FAIL"
        or bool(row.get("Failure Stage"))
    )
    if failed:
        if workload in DIAGNOSTIC_WORKLOADS:
            return (
                ExitCode.CRITICAL,
                f"{prefix} failed, memory errors were detected or the workload aborted",
            )
        return ExitCode.CRITICAL, f"{prefix} did not complete"

    ras_status = str(row.get("RAS Status", "")).upper()
    ras_delta = str(row.get("RAS Error Delta") or "")
    if ras_status == "ERROR":
        return ExitCode.CRITICAL, f"{prefix} uncorrectable errors ({ras_delta})"

    score = f"{row.get('Score')} {row.get('Unit')}"
    warnings = []
    temperature = _number(row.get("Max Temp (C)"))
    if str(row.get("Limit Reason") or "").lower() == "thermal":
        warnings.append(f"thermally throttled at {temperature} C")
    elif temperature is not None and temperature >= GPU_TEMPERATURE_WARN_C:
        warnings.append(f"reached {temperature} C")
    if ras_status == "WARNING":
        counters = [
            token.strip()
            for token in ras_delta.split("||")
            if token.strip() and not any(name in token for name in BENIGN_COUNTERS)
        ]
        if counters:
            warnings.append(f"correctable errors ({', '.join(counters)})")

    if warnings:
        return ExitCode.WARN, f"{prefix} {score}, {'; '.join(warnings)}"
    return ExitCode.OK, f"{prefix} {score}"


@dataclass
class PantheonCheckImpl:
    """Run Pantheon and read its reports."""

    cluster: str
    type: str
    log_level: str
    log_folder: str

    def run_workload(
        self,
        pantheon_bin: Optional[str],
        workload: str,
        devices: List[int],
        duration: int,
        mem_percent: int,
        timeout_secs: int,
        logger: logging.Logger,
    ) -> PantheonRun:
        gpus = ",".join(str(device) for device in devices) if devices else "all"
        cmd = shlex.join(
            [
                pantheon_bin or "pantheon",
                "--test",
                workload,
                "--duration",
                str(duration),
                "--mem",
                str(mem_percent),
                "--gpu",
                gpus,
            ]
        )
        # Pantheon writes its reports below the working directory.
        with tempfile.TemporaryDirectory(prefix="gcm-pantheon-") as workdir:
            full_cmd = f"cd {shlex.quote(workdir)} && {cmd}"
            logger.info(f"Running command '{full_cmd}'")
            command = shell_command(full_cmd, timeout_secs)
            rows, mock = read_reports(pathlib.Path(workdir) / "database", workload)
        return PantheonRun(command=command, rows=rows, mock=mock)


def allocated_devices(
    gpu_devices: Collection[int], check_type: str
) -> Tuple[Optional[List[int]], str]:
    """Return the GPUs to test, or None with the reason when none should be.

    An empty list means every GPU of the node.
    """
    if len(gpu_devices):
        return list(gpu_devices), ""
    if check_type not in ("prolog", "epilog"):
        return [], ""

    devices_env = os.getenv("SLURM_JOB_GPUS") or os.getenv("CUDA_VISIBLE_DEVICES")
    if not devices_env:
        return None, "No GPU is allocated to this job, nothing was tested."
    tokens = [token.strip() for token in devices_env.split(",") if token.strip()]
    if not all(token.isdigit() for token in tokens):
        return (
            None,
            f"Cannot tell which GPUs to test from '{devices_env}', "
            "pass them with --gpu-devices.",
        )
    return [int(token) for token in tokens], ""


@click.command()
@common_arguments
@timeout_argument
@telemetry_argument
@heterogeneous_cluster_v1_option
@click.option(
    "--workload",
    "-w",
    type=str,
    multiple=True,
    default=DEFAULT_WORKLOADS,
    show_default=True,
    help="The Pantheon workload to run. Can be given multiple times.",
)
@click.option(
    "--duration",
    type=click.IntRange(min=1),
    default=30,
    show_default=True,
    help="Seconds to run each workload.",
)
@click.option(
    "--mem-percent",
    type=click.IntRange(min=1, max=99),
    default=99,
    show_default=True,
    help="Percentage of the free GPU memory that a workload may use.",
)
@click.option(
    "--pantheon-bin",
    type=click.Path(dir_okay=False, path_type=pathlib.Path, exists=True),
    help="Path to the pantheon executable. If this option is not given it assumes that pantheon is in PATH.",
)
@click.option(
    "--gpu-devices",
    "-gpu",
    type=click.INT,
    multiple=True,
    help="""The IDs of the GPU devices to test. Can be given multiple IDs.
    If the check is called through prolog or epilog the SLURM_JOB_GPUS or CUDA_VISIBLE_DEVICES variables are used to find the allocated devices, otherwise all the GPUs of the node are tested.
    """,
)
@click.pass_obj
@typechecked
def check_pantheon(
    obj: Optional[PantheonCheck],
    cluster: str,
    type: CHECK_TYPE,
    log_level: LOG_LEVEL,
    log_folder: str,
    timeout: int,
    sink: str,
    sink_opts: Collection[str],
    verbose_out: bool,
    heterogeneous_cluster_v1: bool,
    workload: Collection[str],
    duration: int,
    mem_percent: int,
    pantheon_bin: Optional[pathlib.Path],
    gpu_devices: Collection[int],
) -> None:
    """Run Pantheon GPU diagnostics workloads on the GPUs of the node."""
    if not obj:
        obj = PantheonCheckImpl(cluster, type, log_level, log_folder)

    with HealthCheckRuntime(
        cluster=cluster,
        check_type=type,
        log_level=log_level,
        log_folder=log_folder,
        sink=sink,
        sink_opts=sink_opts,
        verbose_out=verbose_out,
        heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        health_check_name=HealthCheckName.CHECK_PANTHEON,
        killswitch_getter=lambda: FeatureValueHealthChecksFeatures().get_healthchecksfeatures_disable_check_pantheon(),
    ) as rt:
        devices, reason = allocated_devices(gpu_devices, type)
        if devices is None:
            exit_code = ExitCode.OK if reason.startswith("No GPU") else ExitCode.UNKNOWN
            rt.finish(exit_code, reason)
            return

        exit_codes = []
        messages = []
        with EnvCtx({variable: None for variable in DEVICE_VARIABLES}):
            for name in workload:
                try:
                    run = obj.run_workload(
                        str(pantheon_bin) if pantheon_bin else None,
                        name,
                        devices,
                        duration,
                        mem_percent,
                        timeout,
                        rt.logger,
                    )
                except Exception as e:
                    failure = handle_subprocess_exception(e)
                    rt.logger.error(f"{name} generated an exception: {e}")
                    exit_codes.append(ExitCode.WARN)
                    messages.append(f"{name}: could not run, {failure.stdout}")
                    continue

                if not run.rows:
                    # Nothing was measured, so nothing is known about the GPU.
                    tail = (run.command.stdout or "").strip().splitlines()[-3:]
                    exit_codes.append(ExitCode.UNKNOWN)
                    messages.append(
                        f"{name}: pantheon wrote no report "
                        f"(exit code {run.command.returncode}). {' '.join(tail)}"
                    )
                    continue
                if run.mock:
                    exit_codes.append(ExitCode.UNKNOWN)
                    messages.append(
                        f"{name}: pantheon found no GPU with a compiler and ran on "
                        "its CPU backend, no hardware was tested"
                    )
                    continue

                for row in run.rows:
                    exit_code, message = assess_row(row)
                    exit_codes.append(exit_code)
                    messages.append(message)

        overall_exit_code = max(exit_codes or [ExitCode.UNKNOWN])
        rt.finish(overall_exit_code, "\n".join(messages))
