# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import dataclasses
import logging
from pathlib import Path

import pytest
from click.testing import CliRunner
from gcm.health_checks.checks.check_dstate import check_dstate
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclasses.dataclass
class FakeDStateProcessCheckImpl:
    mocked_get_dstate_procs: ShellCommandOut
    mocked_get_strace_of_proc: ShellCommandOut = dataclasses.field(
        default_factory=lambda: FakeShellCommandOut()
    )

    def get_dstate_procs(
        self, elapsed: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.mocked_get_dstate_procs

    def get_strace_of_proc(
        self, pid: str, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.mocked_get_strace_of_proc


def test_dstate_processes_none_found(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    obj = FakeDStateProcessCheckImpl(
        mocked_get_dstate_procs=FakeShellCommandOut(stdout=""),
    )
    result = runner.invoke(
        check_dstate,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=obj,
    )
    assert ExitCode(result.exit_code) == ExitCode.OK


def test_dstate_processes(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)
    obj = FakeDStateProcessCheckImpl(
        mocked_get_dstate_procs=FakeShellCommandOut(stdout="1234 foobar"),
        mocked_get_strace_of_proc=FakeShellCommandOut(returncode=1),
    )
    result = runner.invoke(
        check_dstate,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=obj,
    )
    assert ExitCode(result.exit_code) == ExitCode.CRITICAL


@pytest.mark.parametrize(
    "process_name, expected_exit_code",
    [
        ("foo", ExitCode.CRITICAL),
        ("baz", ExitCode.OK),
        ("foobar", ExitCode.CRITICAL),
    ],
)
def test_dstate_processes_regex_match(
    tmp_path: Path,
    process_name: str,
    expected_exit_code: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)
    obj = FakeDStateProcessCheckImpl(
        mocked_get_dstate_procs=FakeShellCommandOut(stdout="1234 foobar"),
        mocked_get_strace_of_proc=FakeShellCommandOut(returncode=1),
    )
    result = runner.invoke(
        check_dstate,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --process-name={process_name}",
        obj=obj,
    )
    assert ExitCode(result.exit_code) == expected_exit_code
