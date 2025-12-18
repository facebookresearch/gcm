# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_zombie import check_zombie
from gcm.health_checks.subprocess import PipedShellCommandOut
from gcm.health_checks.types import ExitCode


def test_no_zombies(tmp_path: Path) -> None:
    def get_zombie_procs(
        timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_zombie,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=get_zombie_procs,
    )
    assert ExitCode(result.exit_code) == ExitCode.OK


def test_zombies_present(tmp_path: Path) -> None:
    def get_zombie_procs(
        timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        # test output showing presence of zombie processes.
        return PipedShellCommandOut(
            [0, 0], "Z  3  root  [rcu_gp]  7102844\nZ  4  root  [rcu_par_gp]  7102844\n"
        )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_zombie,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=get_zombie_procs,
    )
    assert ExitCode(result.exit_code) == ExitCode.WARN


def test_zombies_exception(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    def get_zombie_procs(
        timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise subprocess.TimeoutExpired(
            ["command line"],
            128,
            "Error command timeout because of timeout setting.\n",
        )

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_zombie,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=get_zombie_procs,
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "Error command timeout because of timeout setting." in caplog.text


def test_zombies_exception_output(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    def get_zombie_procs(
        timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut(
            [0, 0], "Z  3  root  [rcu_gp]\nZ  4  root  [rcu_par_gp]  NOT_A_NUMBER\n"
        )

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_zombie,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=get_zombie_procs,
    )
    assert ExitCode(result.exit_code) == ExitCode.WARN
    assert "Output does not have the expected format" in caplog.text
