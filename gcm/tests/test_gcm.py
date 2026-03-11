# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.monitoring.cli.gcm import main


def _run_cli(
    module: str, args: list[str], timeout: int = 30
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", module] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize("command", main.commands.keys())
def test_cli(command: str) -> None:
    if command == "fsacct":
        pytest.skip(
            "fsacct --help delegates to sacct via subprocess. subprocess output is not captured by CliRunner. Furthermore, we cannot forward to the parent's stdout/stderr (i.e. via `sys.stdout` or `sys.stderr`) because neither are backed by file descriptors at test time."
        )
    runner = CliRunner()

    result = runner.invoke(main, [command, "--help"], catch_exceptions=False)

    assert result.stdout.strip() != ""


def test_backend_option_is_accepted() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--backend", "nvml", "nvml_monitor", "--help"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "--sink" in result.stdout


def test_gcm_backend_nvml_full_run(tmp_path: Path) -> None:
    """Full run: gcm --backend=nvml nvml_monitor --sink=stdout --once"""
    proc = _run_cli(
        "gcm.monitoring.cli.gcm",
        [
            "--backend",
            "nvml",
            "nvml_monitor",
            "--sink",
            "stdout",
            "--once",
            f"--log-folder={tmp_path}",
        ],
    )
    # With GPU: exit 0, stdout has JSON lines (device metrics)
    # Without GPU: exit 1, NVML not found
    if proc.returncode != 0:
        assert "NVML" in proc.stderr or "DeviceTelemetry" in proc.stderr
        return
    lines = [line for line in proc.stdout.strip().split("\n") if line.strip()]
    if not lines:
        pytest.skip("No stdout (no GPU or output not captured)")
    # Stdout sink prints JSON arrays per write
    parsed = json.loads(lines[0])
    assert isinstance(parsed, list) and len(parsed) >= 1
    assert "hostname" in parsed[0] or "gpu_id" in parsed[0]


def test_health_checks_backend_nvml_full_run(tmp_path: Path) -> None:
    """Full run: health_checks --backend=nvml check-nvidia-smi ... --sink=stdout"""
    proc = _run_cli(
        "gcm.health_checks.cli.health_checks",
        [
            "--backend",
            "nvml",
            "check-nvidia-smi",
            "fair_cluster",
            "nagios",
            "--sink",
            "stdout",
            "-c",
            "gpu_num",
            "--gpu_num=0",
            f"--log-folder={tmp_path}",
        ],
    )
    # May fail with gni_lib/ImportError in minimal env - skip in that case
    if "gni_lib" in proc.stderr or "ModuleNotFoundError" in proc.stderr:
        pytest.skip("health_checks requires gni_lib (full test env)")
    # Success: exit 0, stdout has JSON array (may be prefixed by log line)
    assert proc.returncode == 0, f"stderr: {proc.stderr}"
    out = proc.stdout.strip()
    # Extract JSON (may follow "WARNING - ...\n")
    json_start = out.find("[")
    assert json_start >= 0, f"No JSON array in output: {out[:200]}"
    data = json.loads(out[json_start:])
    assert isinstance(data, list) and len(data) >= 1
    row = data[0]
    assert "cluster" in row and "health_check" in row and "result" in row
