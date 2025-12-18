# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_service import package_version, service_status
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeCheckServiceImpl:
    test_command_out: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_service_status(
        self, timeout_secs: int, service: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.test_command_out

    def get_package_rpm_version(
        self, timeout_secs: int, package_name: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.test_command_out


@pytest.fixture
def service_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckServiceImpl:
    """Create FakeCheckServiceImpl object"""
    return FakeCheckServiceImpl(request.param)


pass_service_status = FakeShellCommandOut(
    [],
    0,
    "active",
)

fail_service_status = FakeShellCommandOut(
    [],
    3,
    "inactive",
)


@pytest.mark.parametrize(
    "service_tester, expected",
    [
        (pass_service_status, (ExitCode.OK, "running. Status: active")),
        (
            fail_service_status,
            (ExitCode.CRITICAL, "running. error_code: 3, output: inactive"),
        ),
    ],
    indirect=["service_tester"],
)
def test_service_status(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    service_tester: FakeCheckServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        service_status,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -s randomService",
        obj=service_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_pkg_version = FakeShellCommandOut(
    [],
    0,
    "22.05.6-1.rsc.1",
)
fail_pkg_version = FakeShellCommandOut(
    [],
    0,
    "wrong version",
)
error_rpm_command = FakeShellCommandOut(
    [],
    3,
    "error message",
)


@pytest.mark.parametrize(
    "service_tester, expected",
    [
        (
            pass_pkg_version,
            (ExitCode.OK, "Version is as expected. version: 22.05.6-1.rsc.1"),
        ),
        (
            fail_pkg_version,
            (
                ExitCode.CRITICAL,
                "Version  missmatch. Expected version: 22.05.6-1.rsc.1 and found version: wrong version",
            ),
        ),
        (
            error_rpm_command,
            (
                ExitCode.WARN,
                "rpm command failed. error_code: 3, output: error message",
            ),
        ),
    ],
    indirect=["service_tester"],
)
def test_package_version(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    service_tester: FakeCheckServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        package_version,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p randomService -v 22.05.6-1.rsc.1",
        obj=service_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
