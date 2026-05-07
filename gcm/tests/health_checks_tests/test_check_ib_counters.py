# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_ib_counters health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ib_counters import (
    check_ib_counters,
    process_ib_counters,
)
from gcm.health_checks.types import ExitCode


@dataclass
class FakeIbCountersCheckImpl:
    counters_output: str
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def get_ib_counters(self, logger: logging.Logger) -> str:
        return self.counters_output


@pytest.fixture
def ib_counters_tester(request: pytest.FixtureRequest) -> FakeIbCountersCheckImpl:
    return FakeIbCountersCheckImpl(request.param)


# --- Unit tests for process_ib_counters ---


class TestProcessIbCounters:
    def test_all_zero(self) -> None:
        output = (
            "mlx5_0/1/symbol_error=0\n"
            "mlx5_0/1/link_error_recovery=0\n"
            "mlx5_0/1/link_downed=0\n"
            "mlx5_0/1/port_rcv_errors=0\n"
        )
        exit_code, msg = process_ib_counters(output, threshold=0)
        assert exit_code == ExitCode.OK

    def test_above_threshold_warn(self) -> None:
        output = (
            "mlx5_0/1/symbol_error=5\n"
            "mlx5_0/1/link_downed=0\n"
        )
        exit_code, msg = process_ib_counters(output, threshold=0)
        assert exit_code == ExitCode.WARN
        assert "symbol_error=5" in msg

    def test_link_downed_critical(self) -> None:
        output = (
            "mlx5_0/1/symbol_error=0\n"
            "mlx5_0/1/link_downed=1\n"
        )
        exit_code, msg = process_ib_counters(output, threshold=0)
        assert exit_code == ExitCode.CRITICAL
        assert "link_downed=1" in msg

    def test_custom_threshold(self) -> None:
        output = (
            "mlx5_0/1/symbol_error=5\n"
            "mlx5_0/1/port_rcv_errors=3\n"
        )
        exit_code, msg = process_ib_counters(output, threshold=10)
        assert exit_code == ExitCode.OK

    def test_no_ib_devices(self) -> None:
        exit_code, msg = process_ib_counters("ERROR: no IB devices found", threshold=0)
        assert exit_code == ExitCode.WARN

    def test_empty_counters(self) -> None:
        exit_code, msg = process_ib_counters(
            "ERROR: no IB counters found", threshold=0
        )
        assert exit_code == ExitCode.WARN


# --- Integration tests via CliRunner ---


@pytest.mark.parametrize(
    "ib_counters_tester, expected",
    [
        (
            "mlx5_0/1/symbol_error=0\nmlx5_0/1/link_downed=0",
            (ExitCode.OK, "All IB port counters within threshold"),
        ),
        (
            "mlx5_0/1/link_downed=1",
            (ExitCode.CRITICAL, "link_downed=1"),
        ),
        (
            "mlx5_0/1/symbol_error=10\nmlx5_0/1/link_downed=0",
            (ExitCode.WARN, "symbol_error=10"),
        ),
        (
            "ERROR: no IB devices found",
            (ExitCode.WARN, "no IB devices found"),
        ),
    ],
    indirect=["ib_counters_tester"],
)
def test_check_ib_counters(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ib_counters_tester: FakeIbCountersCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_ib_counters,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=ib_counters_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
