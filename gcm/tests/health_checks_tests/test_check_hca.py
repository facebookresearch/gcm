# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_hca import check_hca
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut

sample_output = """4 HCAs found:
    mlx5_0
    mlx5_1
    mlx5_2
    mlx5_3

"""

sample_output_single_hca = """1 HCA found:
    mlx5_0

"""


@pytest.mark.parametrize(
    "expected_count, expected_result",
    [
        ((4, sample_output), ExitCode.OK),
        ((8, sample_output), ExitCode.CRITICAL),
        ((2, sample_output), ExitCode.WARN),
        ((1, sample_output_single_hca), ExitCode.OK),
    ],
)
def test_check_hca(
    tmp_path: Path,
    expected_count: Tuple[int, str],
    expected_result: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(cmd: str, logger: logging.Logger) -> ShellCommandOut:
        return FakeShellCommandOut([], 0, expected_count[1])

    args = f"fair_cluster prolog --log-folder={tmp_path} --expected-count={expected_count[0]} --sink=do_nothing"

    result = runner.invoke(
        check_hca,
        args,
        obj=mock_shell_command,
    )

    assert result.exit_code == expected_result.value
