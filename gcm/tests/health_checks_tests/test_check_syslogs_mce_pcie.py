# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_syslogs import check_syslogs
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSyslogMcePcieImpl:
    syslog_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_link_flap_report(
        self, syslog_file: Path, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        raise NotImplementedError

    def get_xid_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise NotImplementedError

    def get_io_error_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise NotImplementedError

    def get_mce_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut(
            [self.syslog_out.returncode], self.syslog_out.stdout
        )

    def get_pcie_aer_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut(
            [self.syslog_out.returncode], self.syslog_out.stdout
        )


@pytest.fixture
def fake_mce_pcie_tester(
    request: pytest.FixtureRequest,
) -> FakeSyslogMcePcieImpl:
    return FakeSyslogMcePcieImpl(request.param)


no_mce_error = FakeShellCommandOut([], 0, "")

command_error = FakeShellCommandOut([], 2, "ERROR happened")

with_mce_errors = FakeShellCommandOut(
    [],
    0,
    "[12345.678] mce: [Hardware Error]: Machine check events logged\n[12345.679] mce: [Hardware Error]: CPU 0: Machine Check",
)

no_pcie_error = FakeShellCommandOut([], 0, "")

with_pcie_corrected_errors = FakeShellCommandOut(
    [],
    0,
    "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0",
)

with_pcie_uncorrectable_errors = FakeShellCommandOut(
    [],
    0,
    "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0\n[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable error received: 0000:02:00.0",
)


@pytest.mark.parametrize(
    "fake_mce_pcie_tester, expected",
    [
        (no_mce_error, (ExitCode.OK, "No MCE errors detected.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code: {command_error.returncode} output: {command_error.stdout}",
            ),
        ),
        (
            with_mce_errors,
            (
                ExitCode.CRITICAL,
                "2 MCE error(s) detected.",
            ),
        ),
    ],
    indirect=["fake_mce_pcie_tester"],
)
def test_mce(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_mce_pcie_tester: FakeSyslogMcePcieImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"mce fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_mce_pcie_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "fake_mce_pcie_tester, expected",
    [
        (no_pcie_error, (ExitCode.OK, "No PCIe AER errors detected.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code: {command_error.returncode} output: {command_error.stdout}",
            ),
        ),
        (
            with_pcie_corrected_errors,
            (
                ExitCode.WARN,
                "1 PCIe AER corrected error(s) detected.",
            ),
        ),
        (
            with_pcie_uncorrectable_errors,
            (
                ExitCode.CRITICAL,
                "2 PCIe AER error(s) detected, including uncorrectable.",
            ),
        ),
    ],
    indirect=["fake_mce_pcie_tester"],
)
def test_pcie_aer(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_mce_pcie_tester: FakeSyslogMcePcieImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"pcie-aer fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_mce_pcie_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
