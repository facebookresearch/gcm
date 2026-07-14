# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from subprocess import CompletedProcess
from typing import Tuple

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_authentication import (
    check_path_access_by_user,
    password_status,
)
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode


@dataclass
class FakeAuthenticationCheckImpl:
    auth_test: CompletedProcess

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_pass_status(
        self, timeout_secs: int, user: str, sudo: bool, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut(
            [self.auth_test.returncode, 0], self.auth_test.stdout
        )

    def check_file_readable_by_user(
        self, timeout_secs: int, path: str, user: str, op: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.auth_test


@pytest.fixture
def auth_tester(
    request: pytest.FixtureRequest,
) -> FakeAuthenticationCheckImpl:
    """
    Create FakeAuthenticationCheckImpl object
    """
    return FakeAuthenticationCheckImpl(request.param)


@pytest.mark.parametrize(
    "auth_tester, expected_arg, expected",
    [
        # CentOS 9 long-form output matches long-form expected
        (
            CompletedProcess(args=[], returncode=0, stdout="PS\n"),
            "PS",
            (ExitCode.OK, "Password status as expected: PS"),
        ),
        # CentOS 10 short-form output matches long-form expected (alias)
        (
            CompletedProcess(args=[], returncode=0, stdout="P\n"),
            "PS",
            (ExitCode.OK, "Password status as expected: PS"),
        ),
        # CentOS 10 short-form locked matches long-form locked expected (alias)
        (
            CompletedProcess(args=[], returncode=0, stdout="L\n"),
            "LK",
            (ExitCode.OK, "Password status as expected: LK"),
        ),
        # CentOS 9 long-form locked still works
        (
            CompletedProcess(args=[], returncode=0, stdout="LK\n"),
            "LK",
            (ExitCode.OK, "Password status as expected: LK"),
        ),
        # Genuine mismatch: no-password when password expected → CRITICAL
        (
            CompletedProcess(args=[], returncode=0, stdout="NP\n"),
            "PS",
            (ExitCode.CRITICAL, "'NP'"),
        ),
        # Locked when password expected → CRITICAL (both forms)
        (
            CompletedProcess(args=[], returncode=0, stdout="L\n"),
            "PS",
            (ExitCode.CRITICAL, "'L'"),
        ),
        (
            CompletedProcess(args=[], returncode=2, stdout="Error"),
            "PS",
            (
                ExitCode.WARN,
                "passwd command FAILED to execute. error_code: 2 output: Error",
            ),
        ),
    ],
    indirect=["auth_tester"],
)
def test_pass_status(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    auth_tester: FakeAuthenticationCheckImpl,
    expected_arg: str,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        password_status,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -u userA -s {expected_arg}",
        obj=auth_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "auth_tester, expected",
    [
        (CompletedProcess(args=[], returncode=0, stdout=""), ExitCode.OK),
        (CompletedProcess(args=[], returncode=1, stdout=""), ExitCode.CRITICAL),
    ],
    indirect=["auth_tester"],
)
def test_check_path_access_by_user(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    auth_tester: FakeAuthenticationCheckImpl,
    expected: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_path_access_by_user,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -u userA -p /path",
        obj=auth_tester,
    )

    assert result.exit_code == expected.value
