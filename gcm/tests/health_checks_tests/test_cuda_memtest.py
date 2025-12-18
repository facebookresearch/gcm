# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from pathlib import Path
from typing import Optional

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_memtest import memtest
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@pytest.mark.parametrize(
    "size, expected",
    [
        (
            100,
            ExitCode.CRITICAL,
        ),
        (
            10,
            ExitCode.OK,
        ),
    ],
)
def test_cuda_memtest(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, size: int, expected: ExitCode
) -> None:
    def fake_cuda_memtest(
        bin_path: Optional[str],
        device_id: int,
        alloc_size_gb: int,
        timeout: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        if alloc_size_gb <= 16:
            return FakeShellCommandOut([], 0, "Success.")
        else:
            return FakeShellCommandOut([], 2, "Error in allocating cuda memory.")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        memtest,
        f"fair_cluster prolog --log-folder={tmp_path} --size={size} --sink=do_nothing -gpu 0 -gpu 1",
        obj=fake_cuda_memtest,
    )
    assert result.exit_code == expected.value


@pytest.mark.parametrize(
    "size, expected",
    [
        (
            100,
            ExitCode.CRITICAL,
        ),
        (
            10,
            ExitCode.OK,
        ),
    ],
)
def test_cuda_memtest_env_variables(
    tmp_path: Path, size: int, expected: ExitCode
) -> None:
    def fake_cuda_memtest(
        bin_path: Optional[str],
        device_id: int,
        alloc_size_gb: int,
        timeout: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        if alloc_size_gb <= 16:
            return FakeShellCommandOut([], 0, "Success.")
        else:
            return FakeShellCommandOut([], 2, "Error in allocating cuda memory.")

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        memtest,
        f"fair_cluster prolog --log-folder={tmp_path} --size={size} --sink=do_nothing",
        obj=fake_cuda_memtest,
        env={"CUDA_VISIBLE_DEVICES": "1"},
    )
    assert result.exit_code == expected.value


def test_cuda_memtest_exception(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    def fake_cuda_memtest(
        bin_path: Optional[str],
        device_id: int,
        alloc_size_gb: int,
        timeout: int,
        logger: logging.Logger,
    ) -> ShellCommandOut:
        raise subprocess.TimeoutExpired(
            ["command line"],
            128,
            "Error command timeout because of timeout setting.\n",
        )

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        memtest,
        f"fair_cluster prolog --log-folder={tmp_path} --size=10 --sink=do_nothing -gpu 0",
        obj=fake_cuda_memtest,
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "Error command timeout because of timeout setting." in caplog.text
