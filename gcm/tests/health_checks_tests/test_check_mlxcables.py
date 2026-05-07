# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_mlxcables health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_mlxcables import (
    check_mlxcables,
    process_cable_ddm,
)
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeMlxcablesCheckImpl:
    devices: List[str]
    ddm_outputs: dict[str, FakeShellCommandOut]
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def list_cable_devices(self, logger: logging.Logger) -> List[str]:
        return self.devices

    def get_cable_ddm(
        self, device: str, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.ddm_outputs[device]


# --- Unit tests for process_cable_ddm ---


class TestProcessCableDdm:
    def test_healthy(self) -> None:
        exit_code, msg = process_cable_ddm(
            "/dev/mst/mt1234_cable_0",
            "Temperature: 35.0 C\nVoltage: 3.3 V\n",
            0,
        )
        assert exit_code == ExitCode.OK

    def test_warning(self) -> None:
        exit_code, msg = process_cable_ddm(
            "/dev/mst/mt1234_cable_0",
            "Temperature: 85.0 C WARNING\nVoltage: 3.3 V\n",
            0,
        )
        assert exit_code == ExitCode.WARN
        assert "WARNING" in msg

    def test_alarm(self) -> None:
        exit_code, msg = process_cable_ddm(
            "/dev/mst/mt1234_cable_0",
            "Temperature: 95.0 C ALARM\nVoltage: 3.3 V\n",
            0,
        )
        assert exit_code == ExitCode.WARN
        assert "ALARM" in msg

    def test_both_warning_and_alarm(self) -> None:
        exit_code, msg = process_cable_ddm(
            "/dev/mst/mt1234_cable_0",
            "Temperature: 95.0 C ALARM\nRX Power: -5.0 dBm WARNING\n",
            0,
        )
        assert exit_code == ExitCode.WARN
        assert "ALARM" in msg
        assert "WARNING" in msg

    def test_command_failure(self) -> None:
        exit_code, msg = process_cable_ddm(
            "/dev/mst/mt1234_cable_0",
            "error",
            1,
        )
        assert exit_code == ExitCode.WARN
        assert "failed" in msg


# --- Integration tests via CliRunner ---


@pytest.fixture
def mlxcables_tester(request: pytest.FixtureRequest) -> FakeMlxcablesCheckImpl:
    return FakeMlxcablesCheckImpl(**request.param)


@pytest.mark.parametrize(
    "mlxcables_tester, expected",
    [
        (
            {
                "devices": ["/dev/mst/mt1_cable_0"],
                "ddm_outputs": {
                    "/dev/mst/mt1_cable_0": FakeShellCommandOut(
                        stdout="Temperature: 35.0 C\nVoltage: 3.3 V"
                    ),
                },
            },
            (ExitCode.OK, "healthy"),
        ),
        (
            {
                "devices": ["/dev/mst/mt1_cable_0"],
                "ddm_outputs": {
                    "/dev/mst/mt1_cable_0": FakeShellCommandOut(
                        stdout="Temperature: 95.0 C ALARM"
                    ),
                },
            },
            (ExitCode.WARN, "ALARM"),
        ),
        (
            {
                "devices": [],
                "ddm_outputs": {},
            },
            (ExitCode.UNKNOWN, "No IB cable devices found"),
        ),
    ],
    indirect=["mlxcables_tester"],
)
def test_check_mlxcables(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    mlxcables_tester: FakeMlxcablesCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_mlxcables,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=mlxcables_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
