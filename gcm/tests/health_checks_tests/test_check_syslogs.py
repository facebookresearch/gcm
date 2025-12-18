# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_syslogs import check_syslogs, Syslog
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeSyslogImpl:
    syslog_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_link_flap_report(
        self, syslog_file: Path, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.syslog_out

    def get_xid_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        piped_shell_out: PipedShellCommandOut = PipedShellCommandOut(
            [self.syslog_out.returncode], self.syslog_out.stdout
        )
        return piped_shell_out

    def get_io_error_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        piped_shell_out: PipedShellCommandOut = PipedShellCommandOut(
            [self.syslog_out.returncode], self.syslog_out.stdout
        )
        return piped_shell_out


@pytest.fixture
def fake_syslog_tester(
    request: pytest.FixtureRequest,
) -> FakeSyslogImpl:
    """Create FakeSyslogImpl object"""
    return FakeSyslogImpl(request.param)


no_link_flap = FakeShellCommandOut([], 0, "")

link_flap_error = FakeShellCommandOut(
    [],
    2,
    "ERROR happened",
)

with_link_flaps = FakeShellCommandOut(
    [],
    0,
    """
Dec  6 19:25:33 at7tj000004 systemd-networkd[2385]: eth0: Lost carrier
Dec  6 19:25:33 at7tj000004 systemd-networkd[2385]: ib1: Lost carrier""",
)


@pytest.mark.parametrize(
    "fake_syslog_tester, expected",
    [
        (no_link_flap, (ExitCode.OK, "No link flaps were detected")),
        (
            link_flap_error,
            (
                ExitCode.WARN,
                f"link flap command FAILED to execute. error_code: {link_flap_error.returncode} output: {link_flap_error.stdout}",
            ),
        ),
        (
            with_link_flaps,
            (
                ExitCode.CRITICAL,
                "eth link flap detected.\nib link flap detected.\n",
            ),
        ),
    ],
    indirect=["fake_syslog_tester"],
)
def test_link_flaps(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_syslog_tester: FakeSyslogImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"link-flaps fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_syslog_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


no_xid_error = FakeShellCommandOut([], 0, "")

command_error = FakeShellCommandOut([], 2, "ERROR happened")

with_critical_xid_error = FakeShellCommandOut(
    [],
    0,
    """
[Fri Oct 14 14:56:49 2022] NVRM: Xid (PCI:000d:00:00): 31, pid=3234, Graphics SM Warp Exception on (GPC 2, TPC 2, SM 1): Out Of Range Address
[Fri Oct 14 14:56:49 2022] NVRM: Xid (PCI:000d:00:00): 48, pid=3234, Graphics SM Global Exception on (GPC 2, TPC 2, SM 1): Multiple Warp Errors""",
)

with_warning_xid_error = FakeShellCommandOut(
    [],
    0,
    """
[Fri Oct 14 14:56:49 2022] NVRM: Xid (PCI:000d:00:00): 31, pid=3234, Graphics SM Warp Exception on (GPC 2, TPC 2, SM 1): Out Of Range Address""",
)


@pytest.mark.parametrize(
    "fake_syslog_tester, expected",
    [
        (no_xid_error, (ExitCode.OK, "No XID error was found.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code: {command_error.returncode} output: {command_error.stdout}",
            ),
        ),
        (
            with_critical_xid_error,
            (
                ExitCode.CRITICAL,
                "non-critical XID error: 31, XID causes: Driver Error, HW Error, User App Error. XID error: 48, XID causes: HW Error. ",
            ),
        ),
        (
            with_warning_xid_error,
            (
                ExitCode.WARN,
                "non-critical XID error: 31, XID causes: Driver Error, HW Error, User App Error. ",
            ),
        ),
    ],
    indirect=["fake_syslog_tester"],
)
def test_xid(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_syslog_tester: FakeSyslogImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"xid fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_syslog_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


no_io_error = FakeShellCommandOut([], 0, "")

""" Example of an error message
[470907.282230] blk_update_request: I/O error, dev nvme2n1, sector 6442712256 op 0x1:(WRITE) flags 0x1000 phys_seg 8 prio class 0
[470907.303529] blk_update_request: I/O error, dev nvme2n1, sector 264192 op 0x1:(WRITE) flags 0x1000 phys_seg 4 prio class 0
[470907.314560] blk_update_request: I/O error, dev nvme2n1, sector 2147747008 op 0x1:(WRITE) flags 0x1000 phys_seg 8 prio class 0
[470911.895805] XFS (md127): log I/O error -5
[470911.895902] XFS (md127): log I/O error -5
"""
with_io_error = FakeShellCommandOut([], 0, "nvme2n1")


@pytest.mark.parametrize(
    "fake_syslog_tester, expected",
    [
        (no_io_error, (ExitCode.OK, "No IO errors detected.")),
        (
            command_error,
            (
                ExitCode.WARN,
                f"dmesg command FAILED to execute. error_code: {command_error.returncode} output: {command_error.stdout}",
            ),
        ),
        (
            with_io_error,
            (
                ExitCode.CRITICAL,
                "IO error detected on: nvme2n1",
            ),
        ),
    ],
    indirect=["fake_syslog_tester"],
)
def test_io_errors(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    fake_syslog_tester: FakeSyslogImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_syslogs,
        f"io-errors fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_syslog_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "check",
    ["link-flaps", "xid", "io-errors"],
)
def test_exception_handling(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, check: str
) -> None:
    @dataclass
    class ExceptionSyslogObject:
        cluster: str
        type: str
        log_level: str
        log_folder: str

        def get_link_flap_report(
            self, syslog_file: Path, timeout_secs: int, logger: logging.Logger
        ) -> ShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

        def get_xid_report(
            self, timeout_secs: int, logger: logging.Logger
        ) -> PipedShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

        def get_io_error_report(
            self, timeout_secs: int, logger: logging.Logger
        ) -> PipedShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

    runner = CliRunner(mix_stderr=False)
    fake_syslog_obj: Syslog = ExceptionSyslogObject(
        "cluster", "type", "log_level", "log_folder"
    )
    caplog.at_level(logging.INFO)
    result = runner.invoke(
        check_syslogs,
        f"{check} fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=fake_syslog_obj,
    )
    assert result.exit_code == ExitCode.WARN.value
    assert "Error command timeout because of timeout setting." in caplog.text
