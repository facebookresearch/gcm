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
    process_pcie_aer_output,
)
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSyslogPcieImpl:
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
        raise NotImplementedError

    def get_pcie_aer_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut(
            [self.syslog_out.returncode], self.syslog_out.stdout
        )


@pytest.fixture
def fake_pcie_tester(
    request: pytest.FixtureRequest,
) -> FakeSyslogPcieImpl:
    return FakeSyslogPcieImpl(request.param)


no_pcie_error = FakeShellCommandOut([], 0, "")

command_error = FakeShellCommandOut([], 2, "ERROR happened")

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
        assert "info=1" in msg

    def test_uncorrectable_nonfatal_is_warn(self) -> None:
        output = (
            "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.WARN
        assert "warn=1" in msg

    def test_uncorrectable_fatal_is_critical(self) -> None:
        output = "[12345.680] pcieport 0000:00:03.0: AER: Uncorrectable (Fatal) error"
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "critical=1" in msg

    def test_cant_recover_is_critical(self) -> None:
        output = (
            "[12345.680] nvidia 0000:01:00.0: AER: "
            "can't recover (no error_detected callback)"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "critical=1" in msg

    def test_mixed_corrected_and_fatal(self) -> None:
        output = (
            "[12345.678] pcieport 0000:00:01.0: AER: Corrected error received\n"
            "[12345.679] pcieport 0000:00:02.0: AER: Uncorrectable (Fatal) error"
        )
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.CRITICAL
        assert "critical=1" in msg
        assert "info=1" in msg

    def test_corrected_inside_uncorrectable_is_ok(self) -> None:
        """A line with both 'Uncorrectable' and 'Corrected error' should be OK."""
        output = "[12345.690] pcieport 0000:00:01.0: AER: Corrected error in Uncorrectable context"
        exit_code, msg = process_pcie_aer_output(output, 0)
        assert exit_code == ExitCode.OK
        assert "info=1" in msg


@pytest.mark.parametrize(
    "fake_pcie_tester, expected",
    [
        (no_pcie_error, (ExitCode.OK, "No PCIe AER errors detected.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code={command_error.returncode}, output='{command_error.stdout}'",
            ),
        ),
        (
            with_pcie_corrected_errors,
            (
                ExitCode.OK,
                "1 PCIe AER error(s) detected (info=1).",
            ),
        ),
        (
            with_pcie_uncorrectable_nonfatal,
            (
                ExitCode.WARN,
                "2 PCIe AER error(s) detected (warn=1, info=1).",
            ),
        ),
        (
            with_pcie_uncorrectable_fatal,
            (
                ExitCode.CRITICAL,
                "2 PCIe AER error(s) detected (critical=1, info=1).",
            ),
        ),
        (
            with_pcie_cant_recover,
            (
                ExitCode.CRITICAL,
                "1 PCIe AER error(s) detected (critical=1).",
            ),
        ),
    ],
    indirect=["fake_pcie_tester"],
)
def test_pcie_aer(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_pcie_tester: FakeSyslogPcieImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"pcie-aer fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_pcie_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
