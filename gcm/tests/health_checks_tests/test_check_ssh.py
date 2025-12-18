# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_ssh import ssh_connection
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeCheckSSHServiceImpl:
    test_command_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def try_ssh_connection(
        self, timeout_secs: int, hostaddress: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.test_command_out


@pytest.fixture
def ssh_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckSSHServiceImpl:
    """Create FakeCheckSSHServiceImpl object"""
    return FakeCheckSSHServiceImpl(request.param)


pass_ssh_connection = FakeShellCommandOut(
    [],
    0,
    "",
)

fail_ssh_connection = FakeShellCommandOut(
    [],
    255,
    "ssh: connect to host testHost port 22: No route to host",
)


@pytest.mark.parametrize(
    "ssh_tester, expected",
    [
        (pass_ssh_connection, (ExitCode.OK, "ssh connection succeeded")),
        (
            fail_ssh_connection,
            (
                ExitCode.CRITICAL,
                "ssh connection failed. error_code: 255, output: ssh: connect to host testHost port 22: No route to host",
            ),
        ),
    ],
    indirect=["ssh_tester"],
)
def test_ssh_connection(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    ssh_tester: FakeCheckSSHServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        ssh_connection,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --host testHost",
        obj=ssh_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
