# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_dcgmi import check_dcgmi, DCGM, diag, nvlink
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeDCGMImpl:
    shell_out: ShellCommandOut
    piped_shell_out: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_diagnostics(
        self, level: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.shell_out

    def get_nvlink_error_report(
        self, gpu_index: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return self.shell_out

    def get_nvlink_status_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.piped_shell_out


@pytest.fixture
def dcgmi_shell_command_tester(
    request: pytest.FixtureRequest,
) -> FakeDCGMImpl:
    """Create FakeDCGMImpl object"""
    return FakeDCGMImpl(request.param, PipedShellCommandOut([0], "dummy output"))


diag_pass_output = FakeShellCommandOut(
    [],
    0,
    '{"DCGM GPU Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "Blacklist", "results": [{"status": "Pass"}]}, {"name": "NVML Library", "results": [{"status": "Pass"}]}, {"name": "CUDA Main Library", "results": [{"status": "Pass"}]}, {"name": "Permissions and OS Blocks", "results": [{"status": "Pass"}]}, {"name": "Persistence Mode", "results": [{"status": "Pass"}]}, {"name": "Environment Variables", "results": [{"status": "Pass"}]}, {"name": "Page Retirement/Row Remap", "results": [{"status": "Pass"}]}, {"name": "Graphics Processes", "results": [{"status": "Pass"}]}, {"name": "Inforom", "results": [{"status": "Pass"}]}]}]}}',
)
# DCGM 4.x uses "DCGM Diagnostic" instead of "DCGM GPU Diagnostic" and has test_summary
diag_pass_output_v4 = FakeShellCommandOut(
    [],
    0,
    '{"DCGM Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "software", "results": [{"entity_group": "GPU", "entity_group_id": 1, "entity_id": 0, "status": "Pass"}], "test_summary": {"status": "Pass"}}]}]}}',
)
diag_fail_output_v4 = FakeShellCommandOut(
    [],
    0,
    '{"DCGM Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "software", "results": [{"entity_group": "GPU", "entity_group_id": 1, "entity_id": 0, "status": "Fail"}], "test_summary": {"status": "Fail"}}]}]}}',
)
diag_fail_output = FakeShellCommandOut(
    [],
    0,
    '{"DCGM GPU Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "Blacklist", "results": [{"status": "Pass"}]}, {"name": "NVML Library", "results": [{"status": "Pass"}]}, {"name": "CUDA Main Library", "results": [{"status": "Pass"}]}, {"name": "Permissions and OS Blocks", "results": [{"status": "Pass"}]}, {"name": "Persistence Mode", "results": [{"status": "Fail"}]}, {"name": "Environment Variables", "results": [{"status": "Warn"}]}, {"name": "Page Retirement/Row Remap", "results": [{"status": "Pass"}]}, {"name": "Graphics Processes", "results": [{"status": "Pass"}]}, {"name": "Inforom", "results": [{"status": "Pass"}]}]}]}}',
)
diag_warn_output = FakeShellCommandOut(
    [],
    0,
    '{"DCGM GPU Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "Blacklist", "results": [{"status": "Pass"}]}, {"name": "NVML Library", "results": [{"status": "Pass"}]}, {"name": "CUDA Main Library", "results": [{"status": "Pass"}]}, {"name": "Permissions and OS Blocks", "results": [{"status": "Pass"}]}, {"name": "Persistence Mode", "results": [{"status": "Warn"}]}, {"name": "Environment Variables", "results": [{"status": "Pass"}]}, {"name": "Page Retirement/Row Remap", "results": [{"status": "Pass"}]}, {"name": "Graphics Processes", "results": [{"status": "Pass"}]}, {"name": "Inforom", "results": [{"status": "Pass"}]}]}]}}',
)
empty_output = FakeShellCommandOut([], 0, "")
error_code_output = FakeShellCommandOut([], 127, "Error message")
non_fatal_error_code_output = FakeShellCommandOut(
    [],
    205,
    '{"DCGM GPU Diagnostic": {"test_categories": [{"category": "Deployment", "tests": [{"name": "Blacklist", "results": [{"status": "Pass"}]}, {"name": "NVML Library", "results": [{"status": "Pass"}]}, {"name": "CUDA Main Library", "results": [{"status": "Pass"}]}, {"name": "Permissions and OS Blocks", "results": [{"status": "Pass"}]}, {"name": "Persistence Mode", "results": [{"status": "Pass"}]}, {"name": "Environment Variables", "results": [{"status": "Pass"}]}, {"name": "Page Retirement/Row Remap", "results": [{"status": "Pass"}]}, {"name": "Graphics Processes", "results": [{"status": "Pass"}]}, {"name": "Inforom", "results": [{"status": "Pass"}]}]}]}}',
)


@pytest.mark.parametrize(
    "dcgmi_shell_command_tester, expected",
    [
        (diag_pass_output, (ExitCode.OK, "All checks passed")),
        (diag_pass_output_v4, (ExitCode.OK, "All checks passed")),  # DCGM 4.x format
        (
            diag_fail_output,
            (
                ExitCode.CRITICAL,
                "Persistence Mode failed.\nEnvironment Variables warning",
            ),
        ),
        (
            diag_fail_output_v4,
            (ExitCode.CRITICAL, "software failed"),
        ),  # DCGM 4.x fail format
        (diag_warn_output, (ExitCode.WARN, "Persistence Mode warning")),
        (empty_output, (ExitCode.WARN, "dcgmi diag FAILED to execute")),
        (
            error_code_output,
            (
                ExitCode.WARN,
                f"dcgmi diag command FAILED to execute. error_code: {error_code_output.returncode} output: {error_code_output.stdout}",
            ),
        ),
        (non_fatal_error_code_output, (ExitCode.OK, "All checks passed")),
    ],
    indirect=["dcgmi_shell_command_tester"],
)
def test_process_dcgmi_diag_output(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    dcgmi_shell_command_tester: FakeDCGMImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        diag,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing",
        obj=dcgmi_shell_command_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


nvlink_error_pass_output = FakeShellCommandOut(
    [],
    0,
    '{"body": {"Link 0": {"children": {"CRC Data Error": {"value": "0"}, "CRC FLIT Error": {"value": "0"}, "Recovery Error": {"value": "0"}, "Replay Error": {"value": "0"}}}, "Link 1": {"children": {"CRC Data Error": {"value": "0"}, "CRC FLIT Error": {"value": "0"}, "Recovery Error": {"value": "0"}, "Replay Error": {"value": "0"}}}}, "header": ["NVLINK Error Counts", "GPU 0"]}',
)
nvlink_error_fail_output = FakeShellCommandOut(
    [],
    0,
    '{"body": {"Link 0": {"children": {"CRC Data Error": {"value": "12"}, "CRC FLIT Error": {"value": "0"}, "Recovery Error": {"value": "0"}, "Replay Error": {"value": "0"}}}, "Link 1": {"children": {"CRC Data Error": {"value": "0"}, "CRC FLIT Error": {"value": "0"}, "Recovery Error": {"value": "0"}, "Replay Error": {"value": "0"}}}}, "header": ["NVLINK Error Counts", "GPU 0"]}',
)


@pytest.mark.parametrize(
    "dcgmi_shell_command_tester, expected",
    [
        (
            nvlink_error_pass_output,
            (ExitCode.OK, "All nvlink error checks passed"),
        ),
        (
            nvlink_error_fail_output,
            (
                ExitCode.CRITICAL,
                "High CRC Data Error count detected link: Link 0, error count: 12",
            ),
        ),
        (
            empty_output,
            (
                ExitCode.WARN,
                "dcgmi nvlink -e command FAILED to execute",
            ),
        ),
        (
            error_code_output,
            (
                ExitCode.WARN,
                f"dcgmi nvlink -e command FAILED to execute. error_code: {error_code_output.returncode} output: {error_code_output.stdout}",
            ),
        ),
    ],
    indirect=["dcgmi_shell_command_tester"],
)
def test_process_dcgmi_nvlink_error_output(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    dcgmi_shell_command_tester: FakeDCGMImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        nvlink,
        f"fair_cluster nagios --log-folder={tmp_path} -c nvlink_errors --data_error_threshold=10 --flit_error_threshold=10 --recovery_error_threshold=10 --replay_error_threshold=10 --sink=do_nothing",
        obj=dcgmi_shell_command_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.fixture
def dcgmi_piped_shell_command_tester(
    request: pytest.FixtureRequest,
) -> FakeDCGMImpl:
    """Create FakeDCGMImpl object"""
    return FakeDCGMImpl(FakeShellCommandOut([], 0, "dummy output"), request.param)


nvlink_status_pass_output = PipedShellCommandOut(
    [0, 0],
    """
    gpuId 0:
        U U U U U U U U U U U U
    gpuId 1:
        U U U U U U U U U U U U""",
)
nvlink_status_fail_output = PipedShellCommandOut(
    [0, 0],
    """
    gpuId 0:
        U U U D U U U U U U U U
    gpuId 1:
        U U U U U U D U U U X X""",
)
piped_empty_output = PipedShellCommandOut([0, 0], "")
piped_error_code_output = PipedShellCommandOut([127, 0], "Error message")


@pytest.mark.parametrize(
    "dcgmi_piped_shell_command_tester, expected",
    [
        (
            nvlink_status_pass_output,
            (ExitCode.OK, "All nvlink links are up for all GPUs"),
        ),
        (
            nvlink_status_fail_output,
            (
                ExitCode.CRITICAL,
                "gpuId 0: has 1 links down and 0 links disabled.\ngpuId 1: has 1 links down and 2 links disabled",
            ),
        ),
        (
            piped_error_code_output,
            (
                ExitCode.WARN,
                "dcgmi nvlink -s command FAILED to execute",
            ),
        ),
        (
            piped_error_code_output,
            (
                ExitCode.WARN,
                f"dcgmi nvlink -s command FAILED to execute. error_code: {piped_error_code_output.returncode[0]} output: {piped_error_code_output.stdout}",
            ),
        ),
    ],
    indirect=["dcgmi_piped_shell_command_tester"],
)
def test_process_dcgmi_nvlink_status_output(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    dcgmi_piped_shell_command_tester: FakeDCGMImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        nvlink,
        f"fair_cluster nagios --log-folder={tmp_path} -c nvlink_status --sink=do_nothing",
        obj=dcgmi_piped_shell_command_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


nvlink_cli_test = [
    ("diag", ""),
    ("nvlink", "-c nvlink_errors"),
    ("nvlink", "-c nvlink_status"),
]


@pytest.mark.parametrize("check, check_params", nvlink_cli_test)
def test_exception_handling(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    check: str,
    check_params: str,
) -> None:
    @dataclass
    class ExceptionDCGMObject:
        cluster: str
        type: str
        log_level: str
        log_folder: str

        def get_diagnostics(
            self, level: int, timeout_secs: int, logger: logging.Logger
        ) -> ShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

        def get_nvlink_error_report(
            self, gpu_index: int, timeout_secs: int, logger: logging.Logger
        ) -> ShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

        def get_nvlink_status_report(
            self, timeout_secs: int, logger: logging.Logger
        ) -> PipedShellCommandOut:
            raise subprocess.TimeoutExpired(
                ["command line"],
                128,
                "Error command timeout because of timeout setting.\n",
            )

    runner = CliRunner(mix_stderr=False)

    fake_dcgm_obj: DCGM = ExceptionDCGMObject(
        "cluster", "type", "log_level", "log_folder"
    )
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_dcgmi,
        f"{check} fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing {check_params}",
        obj=fake_dcgm_obj,
    )
    assert result.exit_code == ExitCode.WARN.value
    assert "Error command timeout because of timeout setting." in caplog.text


@dataclass
class FakeDCGMObject:
    cluster: str
    type: str
    log_level: str
    log_folder: str

    def get_diagnostics(
        self, level: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return diag_pass_output

    def get_nvlink_error_report(
        self, gpu_index: int, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return nvlink_error_pass_output

    def get_nvlink_status_report(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return nvlink_status_pass_output


@pytest.mark.parametrize("check, check_params", nvlink_cli_test)
def test_cli(tmp_path: Path, check: str, check_params: str) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_dcgm_obj: DCGM = FakeDCGMObject("cluster", "type", "log_level", "log_folder")
    result = runner.invoke(
        check_dcgmi,
        f"{check} fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing {check_params}",
        obj=fake_dcgm_obj,
    )
    assert result.exit_code == 0
