import pytest

from gcm.health_checks.types import ExitCode
from gcm.monitoring.device_telemetry_client import ApplicationClockInfo
from gcm.schemas.gpu.application_clock_policy import ClockPolicy, evaluate_clock_policy


def test_evaluate_clock_policy_ok() -> None:
    policy = ClockPolicy(
        expected_graphics_freq=1155,
        expected_memory_freq=1593,
        warn_delta_mhz=30,
        critical_delta_mhz=75,
    )

    result = evaluate_clock_policy(
        ApplicationClockInfo(graphics_freq=1155, memory_freq=1593), policy
    )

    assert result.compliant
    assert result.severity == ExitCode.OK
    assert result.graphics_delta_mhz == 0
    assert result.memory_delta_mhz == 0


def test_evaluate_clock_policy_warn() -> None:
    policy = ClockPolicy(
        expected_graphics_freq=1155,
        expected_memory_freq=1593,
        warn_delta_mhz=30,
        critical_delta_mhz=75,
    )

    result = evaluate_clock_policy(
        ApplicationClockInfo(graphics_freq=1200, memory_freq=1593), policy
    )

    assert not result.compliant
    assert result.severity == ExitCode.WARN


def test_evaluate_clock_policy_critical() -> None:
    policy = ClockPolicy(
        expected_graphics_freq=1155,
        expected_memory_freq=1593,
        warn_delta_mhz=30,
        critical_delta_mhz=75,
    )

    result = evaluate_clock_policy(
        ApplicationClockInfo(graphics_freq=1250, memory_freq=1593), policy
    )

    assert not result.compliant
    assert result.severity == ExitCode.CRITICAL


def test_evaluate_clock_policy_invalid_thresholds() -> None:

    with pytest.raises(ValueError):
        ClockPolicy(
            expected_graphics_freq=1155,
            expected_memory_freq=1593,
            warn_delta_mhz=50,
            critical_delta_mhz=40,
        )
