# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_ib_counters health-check."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_ib_counters import (
    check_ib_counters,
    PortCounters,
    process_ib_counters,
)
from gcm.health_checks.types import ExitCode


# ---------------------------------------------------------------------------
# Fake implementation — injected via click's obj parameter
# ---------------------------------------------------------------------------
@dataclass
class FakeIBCountersCheckImpl:
    """Return pre-configured IB counter data instead of reading sysfs."""

    ports: list[tuple[str, str]] = field(default_factory=list)
    counters: dict[str, dict[str, int]] = field(default_factory=dict)

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def discover_ports(
        self,
        _logger: logging.Logger,
    ) -> list[tuple[str, str]]:
        """Return pre-configured port list."""
        return self.ports

    def read_counter(
        self,
        device: str,
        port: str,
        counter_name: str,
        _logger: logging.Logger,
    ) -> Optional[int]:
        """Return pre-configured counter value."""
        key = f"{device}/{port}"
        return self.counters.get(key, {}).get(counter_name)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
NO_PORTS = FakeIBCountersCheckImpl(ports=[], counters={})

CLEAN_SINGLE_PORT = FakeIBCountersCheckImpl(
    ports=[("mlx5_0", "1")],
    counters={
        "mlx5_0/1": {
            "SymbolErrorCounter": 0,
            "LinkErrorRecoveryCounter": 0,
            "LinkDownedCounter": 0,
            "PortRcvErrors": 0,
            "PortRcvRemotePhysicalErrors": 0,
            "PortRcvSwitchRelayErrors": 0,
            "PortXmitDiscards": 0,
            "PortXmitConstraintErrors": 0,
            "PortRcvConstraintErrors": 0,
            "LocalLinkIntegrityErrors": 0,
            "ExcessiveBufferOverrunErrors": 0,
            "VL15Dropped": 0,
            "PortXmitData": 123456789,
            "PortRcvData": 987654321,
            "PortXmitPkts": 1000000,
            "PortRcvPkts": 2000000,
        },
    },
)

WARN_SINGLE_PORT = FakeIBCountersCheckImpl(
    ports=[("mlx5_0", "1")],
    counters={
        "mlx5_0/1": {
            "SymbolErrorCounter": 5,
            "LinkErrorRecoveryCounter": 0,
            "LinkDownedCounter": 0,
            "PortRcvErrors": 2,
            "PortRcvRemotePhysicalErrors": 0,
            "PortRcvSwitchRelayErrors": 0,
            "PortXmitDiscards": 0,
            "PortXmitConstraintErrors": 0,
            "PortRcvConstraintErrors": 0,
            "LocalLinkIntegrityErrors": 0,
            "ExcessiveBufferOverrunErrors": 0,
            "VL15Dropped": 0,
            "PortXmitData": 100,
            "PortRcvData": 200,
            "PortXmitPkts": 50,
            "PortRcvPkts": 60,
        },
    },
)

CRITICAL_MULTI_PORT = FakeIBCountersCheckImpl(
    ports=[("mlx5_0", "1"), ("mlx5_1", "1")],
    counters={
        "mlx5_0/1": {
            "SymbolErrorCounter": 50,
            "LinkErrorRecoveryCounter": 10,
            "LinkDownedCounter": 5,
            "PortRcvErrors": 30,
            "PortRcvRemotePhysicalErrors": 0,
            "PortRcvSwitchRelayErrors": 0,
            "PortXmitDiscards": 10,
            "PortXmitConstraintErrors": 0,
            "PortRcvConstraintErrors": 0,
            "LocalLinkIntegrityErrors": 0,
            "ExcessiveBufferOverrunErrors": 0,
            "VL15Dropped": 0,
            "PortXmitData": 100,
            "PortRcvData": 200,
            "PortXmitPkts": 50,
            "PortRcvPkts": 60,
        },
        "mlx5_1/1": {
            "SymbolErrorCounter": 0,
            "LinkErrorRecoveryCounter": 0,
            "LinkDownedCounter": 0,
            "PortRcvErrors": 0,
            "PortRcvRemotePhysicalErrors": 0,
            "PortRcvSwitchRelayErrors": 0,
            "PortXmitDiscards": 0,
            "PortXmitConstraintErrors": 0,
            "PortRcvConstraintErrors": 0,
            "LocalLinkIntegrityErrors": 0,
            "ExcessiveBufferOverrunErrors": 0,
            "VL15Dropped": 0,
            "PortXmitData": 300,
            "PortRcvData": 400,
            "PortXmitPkts": 70,
            "PortRcvPkts": 80,
        },
    },
)

CLEAN_MULTI_PORT = FakeIBCountersCheckImpl(
    ports=[("mlx5_0", "1"), ("mlx5_1", "1"), ("mlx5_2", "1"), ("mlx5_3", "1")],
    counters={
        f"mlx5_{i}/1": {
            "SymbolErrorCounter": 0,
            "LinkErrorRecoveryCounter": 0,
            "LinkDownedCounter": 0,
            "PortRcvErrors": 0,
            "PortRcvRemotePhysicalErrors": 0,
            "PortRcvSwitchRelayErrors": 0,
            "PortXmitDiscards": 0,
            "PortXmitConstraintErrors": 0,
            "PortRcvConstraintErrors": 0,
            "LocalLinkIntegrityErrors": 0,
            "ExcessiveBufferOverrunErrors": 0,
            "VL15Dropped": 0,
            "PortXmitData": 1000 * (i + 1),
            "PortRcvData": 2000 * (i + 1),
            "PortXmitPkts": 100 * (i + 1),
            "PortRcvPkts": 200 * (i + 1),
        }
        for i in range(4)
    },
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def ib_counters_tester(
    request: pytest.FixtureRequest,
) -> FakeIBCountersCheckImpl:
    """Create FakeIBCountersCheckImpl object."""
    return request.param


# ---------------------------------------------------------------------------
# Unit tests for the pure process_ib_counters function
# ---------------------------------------------------------------------------
class TestProcessIBCounters:
    """Test the pure processing logic directly without Click."""

    def test_no_ports_returns_warn(self) -> None:
        result = process_ib_counters([], warn_threshold=0, crit_threshold=100)
        assert result.check_status == ExitCode.WARN
        assert "No IB ports discovered" in result.short_out

    def test_clean_port_returns_ok(self) -> None:
        pc = PortCounters(
            device="mlx5_0",
            port="1",
            errors={"SymbolErrorCounter": 0, "PortRcvErrors": 0},
            throughput={"PortXmitData": 12345},
        )
        result = process_ib_counters([pc], warn_threshold=0, crit_threshold=100)
        assert result.check_status == ExitCode.OK
        assert "0 with errors" in result.short_out

    def test_errors_above_warn_threshold(self) -> None:
        pc = PortCounters(
            device="mlx5_0",
            port="1",
            errors={"SymbolErrorCounter": 5, "PortRcvErrors": 3},
            throughput={},
        )
        result = process_ib_counters([pc], warn_threshold=0, crit_threshold=100)
        assert result.check_status == ExitCode.WARN
        assert "1 with errors" in result.short_out
        assert "total_errors=8" in result.short_out

    def test_errors_above_crit_threshold(self) -> None:
        pc = PortCounters(
            device="mlx5_0",
            port="1",
            errors={"SymbolErrorCounter": 80, "PortRcvErrors": 30},
            throughput={},
        )
        result = process_ib_counters([pc], warn_threshold=0, crit_threshold=100)
        assert result.check_status == ExitCode.CRITICAL
        assert "total_errors=110" in result.short_out

    def test_long_out_lists_nonzero_counters(self) -> None:
        pc = PortCounters(
            device="mlx5_0",
            port="1",
            errors={
                "SymbolErrorCounter": 5,
                "PortRcvErrors": 0,
                "LinkDownedCounter": 2,
            },
            throughput={},
        )
        result = process_ib_counters([pc], warn_threshold=0, crit_threshold=100)
        assert len(result.long_out) == 1
        assert "SymbolErrorCounter=5" in result.long_out[0]
        assert "LinkDownedCounter=2" in result.long_out[0]
        assert "PortRcvErrors" not in result.long_out[0]

    def test_multi_port_mixed_errors(self) -> None:
        clean_port = PortCounters(
            device="mlx5_0", port="1",
            errors={"SymbolErrorCounter": 0}, throughput={},
        )
        bad_port = PortCounters(
            device="mlx5_1", port="1",
            errors={"SymbolErrorCounter": 10}, throughput={},
        )
        result = process_ib_counters(
            [clean_port, bad_port], warn_threshold=0, crit_threshold=100,
        )
        assert result.check_status == ExitCode.WARN
        assert "2 ports checked" in result.short_out
        assert "1 with errors" in result.short_out
        assert len(result.long_out) == 1
        assert "mlx5_1/1" in result.long_out[0]

    def test_metrics_emitted_for_all_counters(self) -> None:
        pc = PortCounters(
            device="mlx5_0",
            port="1",
            errors={"SymbolErrorCounter": 0, "PortRcvErrors": 0},
            throughput={"PortXmitData": 999},
        )
        result = process_ib_counters([pc], warn_threshold=0, crit_threshold=100)
        metric_names = [m.name for m in result.short_metrics]
        assert "mlx5_0/1.SymbolErrorCounter" in metric_names
        assert "mlx5_0/1.PortRcvErrors" in metric_names
        assert "mlx5_0/1.PortXmitData" in metric_names


# ---------------------------------------------------------------------------
# Integration tests via Click runner
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("ib_counters_tester", "expected"),
    [
        (
            NO_PORTS,
            (ExitCode.WARN, "No IB ports discovered"),
        ),
        (
            CLEAN_SINGLE_PORT,
            (ExitCode.OK, "1 ports checked, 0 with errors"),
        ),
        (
            WARN_SINGLE_PORT,
            (ExitCode.WARN, "1 ports checked, 1 with errors"),
        ),
        (
            CRITICAL_MULTI_PORT,
            (ExitCode.CRITICAL, "2 ports checked, 1 with errors"),
        ),
        (
            CLEAN_MULTI_PORT,
            (ExitCode.OK, "4 ports checked, 0 with errors"),
        ),
    ],
    indirect=["ib_counters_tester"],
)
def test_check_ib_counters(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ib_counters_tester: FakeIBCountersCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    """Invoke check_ib_counters via Click and verify exit code and output."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ib_counters,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=ib_counters_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    ("ib_counters_tester", "threshold_args", "expected_exit"),
    [
        (
            WARN_SINGLE_PORT,
            "--warn-threshold=10 --crit-threshold=100",
            ExitCode.OK,
        ),
        (
            WARN_SINGLE_PORT,
            "--warn-threshold=0 --crit-threshold=5",
            ExitCode.CRITICAL,
        ),
    ],
    indirect=["ib_counters_tester"],
)
def test_check_ib_counters_custom_thresholds(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ib_counters_tester: FakeIBCountersCheckImpl,
    threshold_args: str,
    expected_exit: ExitCode,
) -> None:
    """Verify that --warn-threshold and --crit-threshold are respected."""
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ib_counters,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing {threshold_args}",
        obj=ib_counters_tester,
    )

    assert result.exit_code == expected_exit.value
