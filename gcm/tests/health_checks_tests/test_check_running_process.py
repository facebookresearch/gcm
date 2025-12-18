# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_running_process import check_running_process
from gcm.health_checks.subprocess import PipedShellCommandOut
from gcm.health_checks.types import ExitCode

pass_running_process = PipedShellCommandOut(
    [0, 0, 0], "user  2228100  8744  0 19:36 ?  00:00:00 randomProcess"
)
fail_running_process = PipedShellCommandOut([0, 0, 0], "")
error_running_process = PipedShellCommandOut([127, 0, 0], "Error message")


@pytest.mark.parametrize(
    "process_status, expected",
    [
        (
            pass_running_process,
            (
                ExitCode.OK,
                "running. output:\n user  2228100  8744  0 19:36 ?  00:00:00 randomProcess",
            ),
        ),
        (
            fail_running_process,
            (
                ExitCode.CRITICAL,
                "not running.",
            ),
        ),
        (
            error_running_process,
            (
                ExitCode.WARN,
                "Command failed. error_code: 127, output:\nError message",
            ),
        ),
    ],
)
def test_service_status(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    process_status: PipedShellCommandOut,
    expected: Tuple[ExitCode, str],
) -> None:
    def test_check_running_process(
        timeout_secs: int, process: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return process_status

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_running_process,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p randomProcess",
        obj=test_check_running_process,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_running_process_exception(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    def test_check_running_process(
        timeout_secs: int, process: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        raise subprocess.TimeoutExpired(
            ["command line"],
            128,
            "Error command timeout because of timeout setting.\n",
        )

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_running_process,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p randomProcess",
        obj=test_check_running_process,
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "Error command timeout because of timeout setting." in caplog.text
