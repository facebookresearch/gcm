# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import pytest
from click.testing import CliRunner

from gcm.health_checks.check_utils.processor_memory_utils import (
    get_mem_attributes,
    known_hostname_mem_mappings,
)
from gcm.health_checks.checks.check_processor import check_processor
from gcm.health_checks.subprocess import PipedShellCommandOut, ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut


@dataclass
class FakeCheckProcessorImpl:
    processor_status: PipedShellCommandOut

    cluster = "test cluster"
    type = "prolog"
    log_level = "INFO"
    log_folder = "/tmp"

    def get_cpu_freq(
        self, timeout_secs: int, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut(
            [], self.processor_status.returncode[0], self.processor_status.stdout
        )

    def get_cpufreq_governor(
        self, timeout_secs: int, sys_freq_file: str, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.processor_status

    def get_mem_info(
        self, timeout_secs: int, logger: logging.Logger
    ) -> PipedShellCommandOut:
        return self.processor_status

    def get_buddyinfo_lines(self, buddyinfo_path: Path) -> Iterable[str]:
        return [
            line.strip()
            for line in filter(None, self.processor_status.stdout.splitlines())
        ]

    def get_clocksource(
        self, timeout_secs: int, sys_clocksource_file: str, logger: logging.Logger
    ) -> ShellCommandOut:
        return FakeShellCommandOut(
            [], self.processor_status.returncode[0], self.processor_status.stdout
        )


@pytest.fixture
def proc_tester(request: pytest.FixtureRequest) -> FakeCheckProcessorImpl:
    """Create FakeCheckProcessorImpl object"""
    return FakeCheckProcessorImpl(request.param)


pass_proc_freq = PipedShellCommandOut([0, 0], "1500")
fail_proc_freq = PipedShellCommandOut([0, 0], "1300")
error_proc_freq = PipedShellCommandOut([1, 0], "Error message")
invalid_out_proc_freq = PipedShellCommandOut([0, 0], "notAnInteger")


@pytest.mark.parametrize(
    "proc_tester, expected",
    [
        (
            pass_proc_freq,
            (
                ExitCode.OK,
                "current processor freq, 1500, is higher or equal than expected, 1400.",
            ),
        ),
        (
            fail_proc_freq,
            (
                ExitCode.CRITICAL,
                "current processor freq, 1300, is lower than expected, 1400.",
            ),
        ),
        (
            error_proc_freq,
            (
                ExitCode.WARN,
                "processor freq command FAILED to execute. error_code: 1 output: Error message",
            ),
        ),
        (
            invalid_out_proc_freq,
            (
                ExitCode.WARN,
                "Invalid processor freq output: notAnInteger.",
            ),
        ),
    ],
    indirect=["proc_tester"],
)
def test_processor_freq(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    proc_tester: FakeCheckProcessorImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_processor,
        f"processor-freq fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --proc_freq=1400",
        obj=proc_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_cpufreq = PipedShellCommandOut([0, 0], "performance")
fail_cpufreq_many_governors = PipedShellCommandOut(
    [0, 0],
    """performance
       powersave""",
)
fail_cpufreq_diff_governor = PipedShellCommandOut([0, 0], "powersave")
error_cpureq = PipedShellCommandOut([1, 0], "Error message")


@pytest.mark.parametrize(
    "proc_tester, expected",
    [
        (
            pass_cpufreq,
            (
                ExitCode.OK,
                "all cpu governors are performance",
            ),
        ),
        (
            fail_cpufreq_many_governors,
            (
                ExitCode.CRITICAL,
                "different governors detected among the cpus",
            ),
        ),
        (
            fail_cpufreq_diff_governor,
            (
                ExitCode.CRITICAL,
                "different governor detected. expected: performance, and found: powersave",
            ),
        ),
        (
            error_cpureq,
            (
                ExitCode.WARN,
                "processor cpufreq governor command FAILED to execute. error_code: 1 output: Error message",
            ),
        ),
    ],
    indirect=["proc_tester"],
)
def test_cpufreq_governor(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    proc_tester: FakeCheckProcessorImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_processor,
        f"cpufreq-governor fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --governor='performance'",
        obj=proc_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


pass_mem_size = PipedShellCommandOut([0, 0], "32 64")
fail_mem_size_dimms = PipedShellCommandOut([0, 0], "31 64")
fail_mem_size_size = PipedShellCommandOut([0, 0], "32 60")
error_mem_size = PipedShellCommandOut([2, 0], "Error")
invalid_out_mem_size = PipedShellCommandOut([0, 0], "Invalid")


@pytest.mark.parametrize(
    "proc_tester, expected",
    [
        (
            pass_mem_size,
            (
                ExitCode.OK,
                "Memory size as expected. DIMMs: 32 and Total size: 2048 GB",
            ),
        ),
        (
            fail_mem_size_dimms,
            (
                ExitCode.CRITICAL,
                "Memory size not as expected. Expected DIMMs/Total size GB: 32/2048 and found 31/1984",
            ),
        ),
        (
            fail_mem_size_size,
            (
                ExitCode.CRITICAL,
                "Memory size not as expected. Expected DIMMs/Total size GB: 32/2048 and found 32/1920",
            ),
        ),
        (
            error_mem_size,
            (
                ExitCode.WARN,
                "dmidecode command FAILED to execute. error_code: 2 output: Error",
            ),
        ),
        (
            invalid_out_mem_size,
            (
                ExitCode.WARN,
                "Invalid output returned: Invalid",
            ),
        ),
    ],
    indirect=["proc_tester"],
)
def test_check_mem_size(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    proc_tester: FakeCheckProcessorImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_processor,
        f"check-mem-size fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing --dimms=32 --total-size=2048",
        obj=proc_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


def test_get_mem_attributes() -> None:
    mem_attributes = get_mem_attributes("rsclearn1034")
    dimms = mem_attributes["dimms"]
    size = mem_attributes["total_size_gb"]
    assert (
        dimms == known_hostname_mem_mappings["rsclearn"]["dimms"]
        and size == known_hostname_mem_mappings["rsclearn"]["total_size_gb"]
    )
    mem_attributes = get_mem_attributes("avalearn1084")
    dimms = mem_attributes["dimms"]
    size = mem_attributes["total_size_gb"]
    assert (
        dimms == known_hostname_mem_mappings["avalearn"]["dimms"]
        and size == known_hostname_mem_mappings["avalearn"]["total_size_gb"]
    )


pass_buddyinfo = PipedShellCommandOut(
    [0],
    """
Node 0, zone      DMA      0      0      0      0      0      0      0      0      1      1      2
Node 0, zone    DMA32      1      2      2      2      1      2      2      1      1      2    745
Node 0, zone   Normal   1434   1018    432    189    114     86     30     11      5      5  93243
Node 1, zone   Normal   1966   1470   1068    655    312    269    213    167    109     63  94116
""",
)
fail_buddyinfo = PipedShellCommandOut(
    [0],
    """
Node 0, zone      DMA      0      0      0      0      0      0      0      0      1      1      2
Node 0, zone    DMA32      1      2      2      2      1      2      2      1      1      2    745
Node 0, zone   Normal   1434   1018    432    189    114     86     30     11      5      5      9
Node 1, zone   Normal   1966   1470   1068    655    312    269    213    167    109     63  94116
""",
)
error_buddyinfo = PipedShellCommandOut(
    [0],
    """
trigger parsing exception on invalid content
""",
)


@pytest.mark.parametrize(
    "proc_tester, expected",
    [
        (
            pass_buddyinfo,
            (
                ExitCode.OK,
                "sufficient number of memory",
            ),
        ),
        (
            fail_buddyinfo,
            (
                ExitCode.CRITICAL,
                "insufficient number of memory blocks of order 8 or higher on node: 0 zone: Normal blocks: [5, 5, 9]",
            ),
        ),
        (
            error_buddyinfo,
            (
                ExitCode.WARN,
                "buddyinfo_lines do not contain required info",
            ),
        ),
    ],
    indirect=["proc_tester"],
)
def test_check_buddyinfo(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    proc_tester: FakeCheckProcessorImpl,
    expected: Tuple[ExitCode, str],
) -> None:
    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_processor,
        f"check-buddyinfo fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing",
        obj=proc_tester,
    )

    assert result.exit_code == expected[0].value
    assert expected[1] in caplog.text


@pytest.mark.parametrize(
    "expected_source, actual_source, expected_result",
    [
        ("tsc", "acpi_pm", ExitCode.CRITICAL),
        ("tsc", "tsc", ExitCode.OK),
    ],
)
def test_check_clocksource(
    tmp_path: Path,
    expected_source: str,
    actual_source: str,
    expected_result: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(cmd: str, logger: logging.Logger) -> ShellCommandOut:
        return FakeShellCommandOut([], 0, actual_source)

    args = f"check-clocksource fair_cluster prolog --log-folder={tmp_path} --expected-source={expected_source} --sink=do_nothing"

    result = runner.invoke(
        check_processor,
        args,
        obj=FakeCheckProcessorImpl(
            processor_status=PipedShellCommandOut([0], actual_source)
        ),
    )

    assert result.exit_code == expected_result.value
