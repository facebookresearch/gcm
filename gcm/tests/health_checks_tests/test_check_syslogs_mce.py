# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_syslogs import check_syslogs, process_mce_output
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSyslogMceImpl:
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
        raise NotImplementedError


@pytest.fixture
def fake_mce_tester(
    request: pytest.FixtureRequest,
) -> FakeSyslogMceImpl:
    return FakeSyslogMceImpl(request.param)


no_mce_error = FakeShellCommandOut([], 0, "")

command_error = FakeShellCommandOut([], 2, "ERROR happened")

# Critical: [Hardware Error] lines
with_mce_hardware_errors = FakeShellCommandOut(
    [],
    0,
    (
        "[12345.678] mce: [Hardware Error]: Machine check events logged\n"
        "[12345.679] mce: [Hardware Error]: CPU 0: Machine Check Exception: 5 Bank 9"
    ),
)

# Warning: corrected errors and thermal throttling
with_mce_corrected_errors = FakeShellCommandOut(
    [],
    0,
    (
        "[12345.678] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.\n"
        "[12345.679] mce: CPU0: Core temperature above threshold, cpu clock throttled"
    ),
)

# Info-only: temperature back to normal
with_mce_info_only = FakeShellCommandOut(
    [],
    0,
    "[12345.680] mce: CPU0: Core temperature/speed normal",
)

# Corrected inside a [Hardware Error] line — should be WARN, not CRITICAL
with_mce_corrected_in_hardware_error = FakeShellCommandOut(
    [],
    0,
    "[12345.690] mce: [Hardware Error]: Corrected error, no action required",
)


class TestProcessMceOutput:
    def test_command_failure(self) -> None:
        exit_code, msg = process_mce_output("ERROR happened", 2)
        assert exit_code == ExitCode.WARN
        assert "FAILED to execute" in msg

    def test_no_errors(self) -> None:
        exit_code, msg = process_mce_output("", 0)
        assert exit_code == ExitCode.OK
        assert "No MCE errors detected" in msg

    def test_hardware_errors_are_critical(self) -> None:
        output = (
            "[12345.678] mce: [Hardware Error]: Machine check events logged\n"
            "[12345.679] mce: [Hardware Error]: CPU 0: Machine Check Exception"
        )
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "critical=2" in msg

    def test_corrected_errors_are_warn(self) -> None:
        output = "[12345.678] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count."
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "warn=1" in msg

    def test_info_only_is_ok(self) -> None:
        output = "[12345.680] mce: CPU0: Core temperature/speed normal"
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.OK
        assert "info=1" in msg

    def test_mixed_severity_uses_highest(self) -> None:
        output = (
            "[12345.678] mce: [Hardware Error]: Machine check events logged\n"
            "[12345.679] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.\n"
            "[12345.680] mce: CPU0: Core temperature/speed normal"
        )
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "critical=1" in msg
        assert "warn=1" in msg
        assert "info=1" in msg

    def test_unknown_mce_line_defaults_to_warn(self) -> None:
        output = "[12345.690] mce: some unknown pattern here"
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "warn=1" in msg

    def test_corrected_inside_hardware_error_is_warn(self) -> None:
        """A line with both [Hardware Error] and Corrected error should be WARN."""
        output = (
            "[12345.690] mce: [Hardware Error]: Corrected error, no action required"
        )
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "warn=1" in msg


@pytest.mark.parametrize(
    "fake_mce_tester, expected",
    [
        (no_mce_error, (ExitCode.OK, "No MCE errors detected.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code={command_error.returncode}, output='{command_error.stdout}'",
            ),
        ),
        (
            with_mce_hardware_errors,
            (ExitCode.CRITICAL, "2 MCE event(s) detected (critical=2)."),
        ),
        (
            with_mce_corrected_errors,
            (ExitCode.WARN, "2 MCE event(s) detected (warn=2)."),
        ),
        (
            with_mce_info_only,
            (ExitCode.OK, "1 MCE event(s) detected (info=1)."),
        ),
        (
            with_mce_corrected_in_hardware_error,
            (ExitCode.WARN, "1 MCE event(s) detected (warn=1)."),
        ),
    ],
    indirect=["fake_mce_tester"],
)
def test_mce(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_mce_tester: FakeSyslogMceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"mce fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_mce_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
