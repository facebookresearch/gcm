# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Test the check_sm_status health-check."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_sm_status import (
    check_sm_status,
    process_sm_info,
)
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSmStatusCheckImpl:
    sm_output: FakeShellCommandOut
    cluster: str = "test cluster"
    type: str = "prolog"
    log_level: str = "INFO"
    log_folder: str = "/tmp"

    def get_sm_info(self, timeout_secs: int, logger: logging.Logger) -> ShellCommandOut:
        return self.sm_output


# --- Unit tests for process_sm_info ---


class TestProcessSmInfo:
    def test_master(self) -> None:
        output = "sminfo: sm lid 1 lmc 0 guid 0x0011223344556677 prio 14 state 3 MASTER"
        exit_code, msg = process_sm_info(output, 0)
        assert exit_code == ExitCode.OK
        assert "MASTER" in msg

    def test_sminfo_master(self) -> None:
        output = "sminfo: sm lid 1 sm guid 0x0011223344556677, activity count 12345678 priority 15 state 3 SMINFO_MASTER"
        exit_code, msg = process_sm_info(output, 0)
        assert exit_code == ExitCode.OK
        assert "MASTER" in msg

    def test_standby(self) -> None:
        output = (
            "sminfo: sm lid 2 lmc 0 guid 0x0011223344556688 prio 10 state 2 STANDBY"
        )
        exit_code, msg = process_sm_info(output, 0)
        assert exit_code == ExitCode.WARN
        assert "STANDBY" in msg

    def test_unreachable(self) -> None:
        exit_code, msg = process_sm_info("", 1)
        assert exit_code == ExitCode.CRITICAL
        assert "unreachable" in msg

    def test_unparseable(self) -> None:
        exit_code, msg = process_sm_info("unexpected output format", 0)
        assert exit_code == ExitCode.WARN
        assert "Could not parse" in msg


# --- Integration tests via CliRunner ---


@pytest.fixture
def sm_status_tester(request: pytest.FixtureRequest) -> FakeSmStatusCheckImpl:
    return FakeSmStatusCheckImpl(request.param)


@pytest.mark.parametrize(
    "sm_status_tester, expected",
    [
        (
            FakeShellCommandOut(
                stdout="sminfo: sm lid 1 lmc 0 guid 0x0011223344556677 prio 14 state 3 MASTER"
            ),
            (ExitCode.OK, "SM reachable, state MASTER"),
        ),
        (
            FakeShellCommandOut(
                stdout="sminfo: sm lid 1 sm guid 0x0011223344556677, activity count 12345678 priority 15 state 3 SMINFO_MASTER"
            ),
            (ExitCode.OK, "SM reachable, state SMINFO_MASTER"),
        ),
        (
            FakeShellCommandOut(
                stdout="sminfo: sm lid 2 lmc 0 guid 0x0011223344556688 prio 10 state 2 STANDBY"
            ),
            (ExitCode.WARN, "STANDBY"),
        ),
        (
            FakeShellCommandOut(returncode=1, stdout=""),
            (ExitCode.CRITICAL, "unreachable"),
        ),
    ],
    indirect=["sm_status_tester"],
)
def test_check_sm_status(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    sm_status_tester: FakeSmStatusCheckImpl,
    expected: tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.set_level(logging.INFO)

    result = runner.invoke(
        check_sm_status,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=sm_status_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
