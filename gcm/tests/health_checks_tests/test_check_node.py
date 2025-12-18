# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_node import check_dnf_repos, check_module, uptime
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeNodeCheckImpl:
    node_test: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_uptime(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.node_test

    def get_module(
        self, timeout_secs: int, module: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.node_test

    def get_dnf_repos(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut(
            [""], self.node_test.returncode[0], self.node_test.stdout
        )


@pytest.fixture
def node_tester(
    request: pytest.FixtureRequest,
) -> FakeNodeCheckImpl:
    """Create FakeNodeCheckImpl object"""
    return FakeNodeCheckImpl(request.param)


pass_uptime = PipedShellCommandOut([0, 0], "12000")
fail_uptime = PipedShellCommandOut([0, 0], "100")
error_uptime = PipedShellCommandOut([127, 0], "Error")
invalid_output = PipedShellCommandOut([0, 0], "InvalidOutput")


@pytest.mark.parametrize(
    "node_tester, expected",
    [
        (pass_uptime, (ExitCode.OK, "Node is up enough time: 12000 secs")),
        (
            fail_uptime,
            (
                ExitCode.WARN,
                "Node recently booted. It's up for: 100 secs",
            ),
        ),
        (
            error_uptime,
            (
                ExitCode.WARN,
                "cat /proc/uptime command FAILED to execute. error_code: 127 output: Error",
            ),
        ),
        (
            invalid_output,
            (
                ExitCode.WARN,
                "Invalid output returned: Invalid",
            ),
        ),
    ],
    indirect=["node_tester"],
)
def test_uptime(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    node_tester: FakeNodeCheckImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        uptime,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --uptime-threshold=600",
        obj=node_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_check_module = PipedShellCommandOut([0, 0], "3")
fail_check_module = PipedShellCommandOut([0, 0], "0")
error_check_module = PipedShellCommandOut([2, 0], "Error")
invalid_out_check_module = PipedShellCommandOut([0, 0], "Invalid")


@pytest.mark.parametrize(
    "node_tester, expected",
    [
        (
            pass_check_module,
            (ExitCode.OK, "Module appears enough times 3 >= 1 threshold"),
        ),
        (
            fail_check_module,
            (
                ExitCode.CRITICAL,
                "Module doesn't appear enough times 0 < 1 threshold",
            ),
        ),
        (
            error_check_module,
            (
                ExitCode.WARN,
                "lsmod command FAILED to execute. error_code: 2 output: Error",
            ),
        ),
        (
            invalid_out_check_module,
            (
                ExitCode.WARN,
                "Invalid output returned: Invalid",
            ),
        ),
    ],
    indirect=["node_tester"],
)
def test_check_module(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    node_tester: FakeNodeCheckImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_module,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -m test_module --mod_count=1",
        obj=node_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_dn_repos = PipedShellCommandOut([0], "OK")
fail_dnf_repos = PipedShellCommandOut([3], "ErrorCommand")
fail_dnf_repos_empty_out = PipedShellCommandOut([0], "")


@pytest.mark.parametrize(
    "node_tester, expected",
    [
        (
            pass_dn_repos,
            (ExitCode.OK, "dnf repos are reachable"),
        ),
        (
            fail_dnf_repos,
            (
                ExitCode.CRITICAL,
                "dnf repos command FAILED to execute. error_code: 3 output: ErrorCommand",
            ),
        ),
        (
            fail_dnf_repos_empty_out,
            (
                ExitCode.CRITICAL,
                "dnf repos command FAILED to execute. error_code: 0 output: ",
            ),
        ),
    ],
    indirect=["node_tester"],
)
def test_check_dnf_repos(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    node_tester: FakeNodeCheckImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_dnf_repos,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=node_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_check_module_value_exception(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    with pytest.raises(ValueError):
        runner.invoke(
            check_module,
            f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -m m1 -m m2 --mod_count=1",
            obj=FakeNodeCheckImpl,
            catch_exceptions=False,
        )
