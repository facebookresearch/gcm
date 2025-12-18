# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import contextlib
import logging
from contextlib import ExitStack

import pytest
from click import Path
from click.testing import CliRunner
from gcm.health_checks.check_utils.output_context_manager import OutputContext
from gcm.health_checks.checks.check_zombie import check_zombie
from gcm.health_checks.subprocess import PipedShellCommandOut
from gcm.health_checks.types import ExitCode

from gcm.schemas.health_check.health_check_name import HealthCheckName
from pytest import CaptureFixture

exit_codes = [
    (ExitCode.OK, "OK"),
    (ExitCode.WARN, "WARNING"),
    (ExitCode.CRITICAL, "CRITICAL"),
]


@pytest.mark.parametrize("exit_code, expected", exit_codes)
def test_output_context_manager(
    capsys: CaptureFixture, exit_code: ExitCode, expected: str
) -> None:
    with ExitStack() as s:
        s.enter_context(
            OutputContext(
                "nagios",
                HealthCheckName.CHECK_ZOMBIE,
                lambda: (exit_code, "random msg"),
                False,
            )
        )

    captured = capsys.readouterr()
    assert f"{expected} - " in captured.out


def test_output_context_manager_exception(capsys: CaptureFixture) -> None:
    with (
        contextlib.suppress(RuntimeError),
        OutputContext(
            "nagios",
            HealthCheckName.CHECK_ZOMBIE,
            lambda: (ExitCode.OK, "random msg"),
            False,
        ),
    ):
        raise RuntimeError("boom")

    captured = capsys.readouterr()
    assert "WARNING - check did not exit normally" in captured.out


def test_output_context_manager_with_command(tmp_path: Path) -> None:
    def get_zombie_procs(
        timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return PipedShellCommandOut([0, 0], "")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_zombie,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing",
        obj=get_zombie_procs,
    )
    assert ExitCode(result.exit_code) == ExitCode.OK
    assert "OK - " in result.output
