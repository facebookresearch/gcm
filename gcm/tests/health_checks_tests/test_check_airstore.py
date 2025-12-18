# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_airstore import check_airstore
from gcm.health_checks.subprocess import PipedShellCommandOut
from gcm.health_checks.types import ExitCode


@dataclass
class FakeCheckAirstoreImpl:
    credential_count: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_credential_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.credential_count


@pytest.fixture
def airstore_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckAirstoreImpl:
    return FakeCheckAirstoreImpl(request.param)


@pytest.mark.parametrize(
    "airstore_tester, expected",
    [
        # Credential count exactly matches
        (
            PipedShellCommandOut([0, 0], "3"),
            ExitCode.OK,
        ),
        # Credential count is less than expected, this is an issue
        (
            PipedShellCommandOut([0, 0], "2"),
            ExitCode.CRITICAL,
        ),
        # Credential count is greater than expected
        (
            PipedShellCommandOut([0, 0], "4"),
            ExitCode.OK,
        ),
        # Issue invoking check
        (
            PipedShellCommandOut([1, 0], ""),
            ExitCode.WARN,
        ),
    ],
    indirect=["airstore_tester"],
)
def test_flash_array_credential_count(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    airstore_tester: FakeCheckAirstoreImpl,
    expected: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_airstore,
        f"flash-array-credential-count fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --expected-count-ge=3",
        obj=airstore_tester,
    )

    assert result.exit_code == expected.value
