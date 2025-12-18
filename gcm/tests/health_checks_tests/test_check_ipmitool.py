# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ipmitool import check_ipmitool
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeIpmitoolCheckImpl:
    sel_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_sel(
        self,
        timeout_secs: int,
        use_ipmitool: bool,
        use_sudo: bool,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        return self.sel_out

    def clear_sel(
        self, timeout_secs: int, output: str, clear_log_threshold: int
    ) -> None:
        pass


@pytest.fixture
def sel_tester(
    request: pytest.FixtureRequest,
) -> FakeIpmitoolCheckImpl:
    """Create FakeIpmitoolCheckImpl object"""
    return FakeIpmitoolCheckImpl(request.param)


pass_sel = FakeShellCommandOut(
    [],
    0,
    """ 1 | 12/24/2022 | 13:58:36 | Voltage #0x4d | Upper Non-critical going high | Asserted
   2 | 01/18/2023 | 14:49:30 | Critical Interrupt #0x90 | Bus Fatal Error | Deasserted""",
)
fail_sel = FakeShellCommandOut(
    [],
    0,
    """ 1 | 12/24/2022 | 13:58:36 | Voltage #0x4d | Upper Non-critical going high | Asserted
  2 | 01/18/2023 | 14:49:30 | Critical Interrupt #0x90 | Bus Fatal Error | Asserted   """,
)
error_sel = FakeShellCommandOut(
    [],
    1,
    "Error message",
)


@pytest.mark.parametrize(
    "sel_tester, expected",
    [
        (pass_sel, (ExitCode.OK, "sel reported no errors.")),
        (
            error_sel,
            (
                ExitCode.WARN,
                "ipmitool sel command FAILED to execute. error_code: 1 output: Error message",
            ),
        ),
        (
            fail_sel,
            (
                ExitCode.CRITICAL,
                "Detected error: Critical Interrupt #0x90, Bus Fatal Error",
            ),
        ),
    ],
    indirect=["sel_tester"],
)
def test_check_sel(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    sel_tester: FakeIpmitoolCheckImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ipmitool,
        f"check-sel fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=sel_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_clear_sel(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    @dataclass
    class FakeIpmitoolCheckImpl:
        cluster = "test cluster"
        type = "prolog"
        log_level = "INFO"
        log_folder = "/tmp"

        def get_sel(
            self,
            timeout_secs: int,
            use_ipmitool: bool,
            use_sudo: bool,
            logger: logging.Logger,
        ) -> ShellCommandOut:
            return pass_sel

        def clear_sel(
            self, timeout_secs: int, output: str, clear_log_threshold: int
        ) -> None:
            raise Exception

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_ipmitool,
        f"check-sel fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --clear_log_threshold=1",
        obj=FakeIpmitoolCheckImpl(),
    )

    assert result.exit_code == ExitCode.WARN.value
