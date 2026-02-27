# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_syslogs import (
    check_syslogs,
    process_mce_output,
    process_pcie_aer_output,
)

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


# -- MCE test data --

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

# Mixed: critical + warning + info
with_mce_mixed = FakeShellCommandOut(
    [],
    0,
    (
        "[12345.678] mce: [Hardware Error]: Machine check events logged\n"
        "[12345.679] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.\n"
        "[12345.680] mce: CPU0: Core temperature/speed normal"
    ),
)

# -- PCIe AER test data --

no_pcie_error = FakeShellCommandOut([], 0, "")

with_pcie_corrected_errors = FakeShellCommandOut(
    [],
    0,
    "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0",
)

with_pcie_uncorrectable_nonfatal = FakeShellCommandOut(
    [],
    0,
    (
        "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0\n"
        "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error received"
    ),
)

with_pcie_uncorrectable_fatal = FakeShellCommandOut(
    [],
    0,
    (
        "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0\n"
        "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Fatal) error received"
    ),
)

with_pcie_cant_recover = FakeShellCommandOut(
    [],
    0,
    "[12345.680] nvidia 0000:01:00.0: AER: can't recover (no error_detected callback)",
)


# ---- Unit tests for process_mce_output ----


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
        assert "2 critical" in msg

    def test_corrected_errors_are_warn(self) -> None:
        output = "[12345.678] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count."
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "1 warning" in msg

    def test_info_only_is_ok(self) -> None:
        output = "[12345.680] mce: CPU0: Core temperature/speed normal"
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.OK
        assert "1 informational" in msg

    def test_mixed_severity_uses_highest(self) -> None:
        output = (
            "[12345.678] mce: [Hardware Error]: Machine check events logged\n"
            "[12345.679] mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.\n"
            "[12345.680] mce: CPU0: Core temperature/speed normal"
        )
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "1 critical" in msg
        assert "1 warning" in msg
        assert "1 informational" in msg

    def test_unknown_mce_line_defaults_to_warn(self) -> None:
        output = "[12345.690] mce: some unknown pattern here"
        exit_code, msg = process_mce_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "1 warning" in msg


# ---- Unit tests for process_pcie_aer_output ----


class TestProcessPcieAerOutput:
    def test_command_failure(self) -> None:
        exit_code, msg = process_pcie_aer_output("ERROR happened", 2)
        assert exit_code == ExitCode.WARN
        assert "FAILED to execute" in msg

    def test_no_errors(self) -> None:
        exit_code, msg = process_pcie_aer_output("", 0)
        assert exit_code == ExitCode.OK
        assert "No PCIe AER errors detected" in msg

    def test_corrected_only_is_ok(self) -> None:
        output = "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received"
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.OK
        assert "1 corrected" in msg

    def test_uncorrectable_nonfatal_is_warn(self) -> None:
        output = (
            "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "1 uncorrectable non-fatal" in msg

    def test_uncorrectable_fatal_is_critical(self) -> None:
        output = "[12345.680] pcieport 0000:00:03.0: AER: Uncorrectable (Fatal) error"
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "1 fatal" in msg

    def test_cant_recover_is_critical(self) -> None:
        output = (
            "[12345.680] nvidia 0000:01:00.0: AER: "
            "can't recover (no error_detected callback)"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "1 fatal" in msg

    def test_mixed_corrected_and_fatal(self) -> None:
        output = (
            "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received\n"
            "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Fatal) error"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "1 fatal" in msg
        assert "1 corrected" in msg


# ---- CLI integration tests ----


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
            with_mce_hardware_errors,
            (
                ExitCode.CRITICAL,
                "2 MCE event(s) detected (2 critical).",
            ),
        ),
        (
            with_mce_corrected_errors,
            (
                ExitCode.WARN,
                "2 MCE event(s) detected (2 warning).",
            ),
        ),
        (
            with_mce_info_only,
            (
                ExitCode.OK,
                "1 MCE event(s) detected (1 informational).",
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
                ExitCode.OK,
                "1 PCIe AER error(s) detected (1 corrected).",
            ),
        ),
        (
            with_pcie_uncorrectable_nonfatal,
            (
                ExitCode.WARN,
                "2 PCIe AER error(s) detected (1 uncorrectable non-fatal, 1 corrected).",
            ),
        ),
        (
            with_pcie_uncorrectable_fatal,
            (
                ExitCode.CRITICAL,
                "2 PCIe AER error(s) detected (1 fatal, 1 corrected).",
            ),
        ),
        (
            with_pcie_cant_recover,
            (
                ExitCode.CRITICAL,
                "1 PCIe AER error(s) detected (1 fatal).",
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
