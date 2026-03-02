# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import socket
import subprocess
from pathlib import Path
from typing import Any, Optional

import pytest
from click import BadParameter
from click.testing import CliRunner

from gcm.health_checks.checks.check_rccl import (
    check_rccl,
    Flavor,
    get_avg_bus_bw,
    get_hosts,
    process_rccl_test_output,
)
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut

# RCCL/rccl-tests output format matches nccl-tests (Avg bus bandwidth line)
SAMPLE_RCCL_SUCCESS_OUTPUT = """
# RCCL test output (same format as nccl-tests)
#       size         count      type   redop    root     time   algbw   busbw
   33554432       8388608     float     sum      -1    344.8   97.32  170.31      0
# Avg bus bandwidth    : 210.99
#
"""

SAMPLE_RCCL_FAILURE_OUTPUT = """
There are not enough slots available in the system to satisfy the 16
slots that were requested by the application.
"""


def test_get_avg_bus_bw_success() -> None:
    out = FakeShellCommandOut([], 0, SAMPLE_RCCL_SUCCESS_OUTPUT)
    assert get_avg_bus_bw(out) == 210.99


def test_get_avg_bus_bw_bus_bandwidth_line() -> None:
    out = FakeShellCommandOut([], 0, "Some output\nBus bandwidth: 100.5\n")
    assert get_avg_bus_bw(out) == 100.5


def test_get_avg_bus_bw_fail_returncode() -> None:
    out = FakeShellCommandOut([], 1, SAMPLE_RCCL_SUCCESS_OUTPUT)
    assert get_avg_bus_bw(out) is None


def test_get_avg_bus_bw_no_bandwidth_line() -> None:
    out = FakeShellCommandOut([], 0, "No bandwidth here")
    assert get_avg_bus_bw(out) is None


@pytest.mark.parametrize(
    "critical_threshold, warn_threshold, expected",
    [
        (200, None, ExitCode.OK),
        (200, 210, ExitCode.OK),
        (210, 211, ExitCode.WARN),
        (211, 211, ExitCode.CRITICAL),
    ],
)
def test_process_rccl_test_output(
    critical_threshold: float,
    warn_threshold: Optional[float],
    expected: ExitCode,
) -> None:
    out = FakeShellCommandOut([], 0, SAMPLE_RCCL_SUCCESS_OUTPUT)
    result = process_rccl_test_output(
        out, "all_reduce", critical_threshold, warn_threshold
    )
    assert result.exitcode == expected


def test_process_rccl_test_output_failed_run() -> None:
    out = FakeShellCommandOut([], 1, "error")
    result = process_rccl_test_output(out, "all_reduce", 10.0, None)
    assert result.exitcode == ExitCode.WARN
    assert "FAILED to run" in result.message


@pytest.mark.parametrize(
    "critical_threshold, warn_threshold, expected",
    [
        (200, None, ExitCode.OK),
        (211, None, ExitCode.CRITICAL),
    ],
)
def test_check_rccl_successful(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    critical_threshold: float,
    warn_threshold: Optional[float],
    expected: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        return FakeShellCommandOut(
            [],
            0,
            SAMPLE_RCCL_SUCCESS_OUTPUT.format(hostname=socket.gethostname()),
        )

    args = (
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing "
        f"-p all_reduce --rccl-tdir /opt/rccl-tests/build/ --critical-threshold {critical_threshold}"
    )
    if warn_threshold is not None:
        args += f" --warn-threshold {warn_threshold}"

    result = runner.invoke(check_rccl, args, obj=mock_runner)
    assert result.exit_code == expected.value
    assert "Avg bus bandwidth" in caplog.text or "RCCL Test" in caplog.text


def test_check_rccl_failure(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        return FakeShellCommandOut([], 0, SAMPLE_RCCL_FAILURE_OUTPUT)

    result = runner.invoke(
        check_rccl,
        (
            f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing "
            "-p all_reduce --rccl-tdir /opt/rccl-tests/build/ --critical-threshold 200"
        ),
        obj=mock_runner,
    )
    assert result.exit_code == ExitCode.WARN.value


def test_check_rccl_exception(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    def mock_runner(cmd: str, timeout: int) -> ShellCommandOut:
        raise subprocess.CalledProcessError(
            255,
            "",
            "Command returned non-zero exit status 255.",
        )

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_rccl,
        (
            f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing "
            "-p all_reduce --rccl-tdir /opt/rccl-tests/build/ --critical-threshold 200"
        ),
        obj=mock_runner,
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "RCCL Test - all_reduce - FAILED to run." in caplog.text


@pytest.mark.parametrize(
    "flavor, hostlist, expected_result",
    [
        ("single", None, [(socket.gethostname(),)]),
        ("single", "node-100", [("node-100",)]),
        (
            "pairwise",
            "node-[100-101]",
            [
                ("node-100", "node-101"),
            ],
        ),
    ],
)
def test_get_hosts_success(
    flavor: Flavor,
    hostlist: str,
    expected_result: Any,
) -> None:
    logger = logging.getLogger(__name__)
    result = get_hosts(flavor, hostlist, logger)
    assert result == expected_result


def test_get_hosts_pairwise_requires_hostlist() -> None:
    logger = logging.getLogger(__name__)
    with pytest.raises(BadParameter):
        get_hosts("pairwise", None, logger)
