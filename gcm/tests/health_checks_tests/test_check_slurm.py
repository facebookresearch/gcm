# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_slurm import (
    cluster_availability,
    node_slurm_state,
    slurmctld_count,
)
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeCheckSlurmServiceImpl:
    slurmctld_count: PipedShellCommandOut
    node_state: ShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_slurmctld_count(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.slurmctld_count

    def get_node_state(
        self, timeout_secs: int, node: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.node_state

    def get_cluster_node_state(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.slurmctld_count


@pytest.fixture
def slurmctld_count_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckSlurmServiceImpl:
    """Create FakeCheckSlurmServiceImpl object"""
    return FakeCheckSlurmServiceImpl(
        request.param, FakeShellCommandOut([], 0, "dummy output")
    )


pass_slurmctld_count = PipedShellCommandOut([0, 0], "2")
error_slurmctld_count = PipedShellCommandOut([127], "Error message")
fail_slurmctld_count = PipedShellCommandOut([0, 0], "1")
invalid_slurmctld_count_output = PipedShellCommandOut([0, 0], "InvalidOutput")


@pytest.mark.parametrize(
    "slurmctld_count_tester, expected",
    [
        (
            pass_slurmctld_count,
            (
                ExitCode.OK,
                "Sufficient slurmctld daemon count. Expected at least: 2 and found: 2",
            ),
        ),
        (
            error_slurmctld_count,
            (
                ExitCode.WARN,
                "scontrol ping command failed to execute. error_code: 127, output: Error message",
            ),
        ),
        (
            fail_slurmctld_count,
            (
                ExitCode.CRITICAL,
                "Insufficient slurmctld daemon count. Expected at least: 2 and found: 1",
            ),
        ),
        (
            invalid_slurmctld_count_output,
            (
                ExitCode.WARN,
                "scontrol ping command invalid output. output: InvalidOutput",
            ),
        ),
    ],
    indirect=["slurmctld_count_tester"],
)
def test_slurmctld_count(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    slurmctld_count_tester: FakeCheckSlurmServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        slurmctld_count,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --slurmctld-count=2",
        obj=slurmctld_count_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.fixture
def node_status_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckSlurmServiceImpl:
    """Create FakeCheckSlurmServiceImpl object"""
    return FakeCheckSlurmServiceImpl(
        PipedShellCommandOut([0], "dummy output"), request.param
    )


pass_node_state = FakeShellCommandOut([], 0, "idle")
fail_node_state = FakeShellCommandOut([], 0, "draining")
invalid_node_state = FakeShellCommandOut([], 0, "randomState")
error_node_state = FakeShellCommandOut([], 2, "Error message")


@pytest.mark.parametrize(
    "node_status_tester, expected",
    [
        (
            pass_node_state,
            (
                ExitCode.OK,
                "node is in good state: idle, and can accept jobs.",
            ),
        ),
        (
            fail_node_state,
            (
                ExitCode.WARN,
                "node is in bad state: draining, and cannot accept jobs.",
            ),
        ),
        (
            invalid_node_state,
            (
                ExitCode.WARN,
                "node is in undefined state: randomState.",
            ),
        ),
        (
            error_node_state,
            (
                ExitCode.WARN,
                "sinfo -n command failed to execute. error_code: 2, output: Error message",
            ),
        ),
    ],
    indirect=["node_status_tester"],
)
def test_node_slurm_state(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    node_status_tester: FakeCheckSlurmServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        node_slurm_state,
        f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=node_status_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.fixture
def cluster_avail_tester(
    request: pytest.FixtureRequest,
) -> FakeCheckSlurmServiceImpl:
    """Create FakeCheckSlurmServiceImpl object"""
    return FakeCheckSlurmServiceImpl(
        request.param, FakeShellCommandOut([], 0, "dummy output")
    )


pass_cluster_avail = PipedShellCommandOut(
    [0, 0],
    """1224 ALLOCATED
      4 DOWN
      6 DOWN+DRAIN
     15 DOWN+DRAIN+NOT_RESPONDING
     22 DOWN+NOT_RESPONDING
      1 DOWN+RESERVED
      1 DOWN+RESERVED+NOT_RESPONDING
      4 IDLE
      5 IDLE+COMPLETING
      7 IDLE+DRAIN
      1 IDLE+DRAIN+INVALID_REG
     14 IDLE+RESERVED
   1800 MIXED
      1 MIXED+COMPLETING
     17 MIXED+DRAIN
""",
)
critical_cluster_avail = PipedShellCommandOut(
    [0, 0],
    """1224 ALLOCATED
      4 DOWN
      6 DOWN+DRAIN
    1498 DOWN+DRAIN+NOT_RESPONDING
     22 DOWN+NOT_RESPONDING
      1 DOWN+RESERVED
      1 DOWN+RESERVED+NOT_RESPONDING
      4 IDLE
      5 IDLE+COMPLETING
      7 IDLE+DRAIN
      1 IDLE+DRAIN+INVALID_REG
     14 IDLE+RESERVED
   1800 MIXED
      1 MIXED+COMPLETING
     17 MIXED+DRAIN
""",
)
warning_cluster_avail = PipedShellCommandOut(
    [0, 0],
    """1224 ALLOCATED
      4 DOWN
      6 DOWN+DRAIN
    800 DOWN+DRAIN+NOT_RESPONDING
     22 DOWN+NOT_RESPONDING
      1 DOWN+RESERVED
      1 DOWN+RESERVED+NOT_RESPONDING
      4 IDLE
      5 IDLE+COMPLETING
      7 IDLE+DRAIN
      1 IDLE+DRAIN+INVALID_REG
     14 IDLE+RESERVED
   1800 MIXED
      1 MIXED+COMPLETING
     17 MIXED+DRAIN
""",
)
error_cluster_avail = PipedShellCommandOut([127], "Error message")
invalid_cluster_avail_output = PipedShellCommandOut([0, 0], "InvalidOutput")


@pytest.mark.parametrize(
    "cluster_avail_tester, expected",
    [
        (
            pass_cluster_avail,
            (
                ExitCode.OK,
                "Nodes in bad state are below the critial and warning thresholds of 25% and 15% respectively.",
            ),
        ),
        (
            critical_cluster_avail,
            (
                ExitCode.CRITICAL,
                "1557 / 4605 = 33.811074918566774% of nodes are in bad slurm state. Critical threshold is 25%",
            ),
        ),
        (
            warning_cluster_avail,
            (
                ExitCode.WARN,
                "859 / 3907 = 21.98617865369849% of nodes are in bad slurm state. Warning threshold is 15%",
            ),
        ),
        (
            error_cluster_avail,
            (
                ExitCode.WARN,
                "scontrol show node command failed to execute. error_code: 127, output: Error message",
            ),
        ),
        (
            invalid_cluster_avail_output,
            (
                ExitCode.WARN,
                "scontrol show node command returned invalid output. output: InvalidOutput",
            ),
        ),
    ],
    indirect=["cluster_avail_tester"],
)
def test_cluster_availability(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    cluster_avail_tester: FakeCheckSlurmServiceImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        cluster_availability,
        f"fair_cluster prolog --log-folder={tmp_path} --critical_threshold=25 --warning_threshold=15 --sink=do_nothing",
        obj=cluster_avail_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text
