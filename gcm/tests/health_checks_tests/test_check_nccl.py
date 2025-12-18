# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import re
import socket
import subprocess
from pathlib import Path
from typing import Any, List, Optional, Tuple

import pytest
from click import BadParameter
from click.testing import CliRunner

from gcm.health_checks.checks.check_nccl import check_nccl, Flavor, get_hosts
from gcm.health_checks.subprocess import ShellCommandOut
from gcm.health_checks.types import ExitCode
from gcm.tests.fakes import FakeShellCommandOut

sample_single_success_output = """
# nThread 1 nGpus 1 minBytes 33554432 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 20 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#  Rank  0 Group  0 Pid  66421 on {hostname} device  0 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  1 Group  0 Pid  66422 on {hostname} device  1 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  2 Group  0 Pid  66423 on {hostname} device  2 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  3 Group  0 Pid  66424 on {hostname} device  3 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  4 Group  0 Pid  66425 on {hostname} device  4 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  5 Group  0 Pid  66428 on {hostname} device  5 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  6 Group  0 Pid  66431 on {hostname} device  6 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  7 Group  0 Pid  66438 on {hostname} device  7 [0x00] NVIDIA A100-SXM4-80GB
NCCL version 2.16.2+cuda11.6
#
#                                                              out-of-place                       in-place
#       size         count      type   redop    root     time   algbw   busbw #wrong     time   algbw   busbw #wrong
#        (B)    (elements)                               (us)  (GB/s)  (GB/s)            (us)  (GB/s)  (GB/s)
    33554432       8388608     float     sum      -1    344.8   97.32  170.31      0    349.5   95.99  167.99      0
    67108864      16777216     float     sum      -1    557.4  120.39  210.68      0    556.2  120.67  211.17      0
   134217728      33554432     float     sum      -1   1149.9  116.72  204.26      0   1149.8  116.73  204.27      0
   268435456      67108864     float     sum      -1   2106.1  127.46  223.05      0   2106.0  127.46  223.06      0
   536870912     134217728     float     sum      -1   4145.6  129.50  226.63      0   4138.5  129.73  227.02      0
  1073741824     268435456     float     sum      -1   8109.1  132.41  231.72      0   8109.7  132.40  231.70      0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 210.99
#
"""

sample_failure_output = """
--------------------------------------------------------------------------
There are not enough slots available in the system to satisfy the 16
slots that were requested by the application:

  /shared/home/abinesh/nccl-tests/build/all_reduce_perf

Either request fewer slots for your application, or make more slots
available for use.

A "slot" is the Open MPI term for an allocatable unit where we can
launch a process.  The number of slots available are defined by the
environment in which Open MPI processes are run:

  1. Hostfile, via "slots=N" clauses (N defaults to number of
     processor cores if not provided)
  2. The --host command line parameter, via a ":N" suffix on the
     hostname (N defaults to 1 if not provided)
  3. Resource manager (e.g., SLURM, PBS/Torque, LSF, etc.)
  4. If none of a hostfile, the --host command line parameter, or an
     RM is present, Open MPI defaults to the number of processor cores

In all the above cases, if you want Open MPI to default to the number
of hardware threads instead of the number of processor cores, use the
--use-hwthread-cpus option.

Alternatively, you can use the --oversubscribe option to ignore the
number of available slots when deciding the number of processes to
launch.
--------------------------------------------------------------------------
"""

sample_pairwise_success_output = """
# nThread 1 nGpus 1 minBytes 33554432 maxBytes 1073741824 step: 2(factor) warmup iters: 5 iters: 20 agg iters: 1 validation: 1 graph: 0
#
# Using devices
#  Rank  0 Group  0 Pid  50781 on {host1} device  0 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  1 Group  0 Pid  50782 on {host1} device  1 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  2 Group  0 Pid  50783 on {host1} device  2 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  3 Group  0 Pid  50784 on {host1} device  3 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  4 Group  0 Pid  50786 on {host1} device  4 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  5 Group  0 Pid  50791 on {host1} device  5 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  6 Group  0 Pid  50795 on {host1} device  6 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  7 Group  0 Pid  50797 on {host1} device  7 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  8 Group  0 Pid  73332 on {host2} device  0 [0x00] NVIDIA A100-SXM4-80GB
#  Rank  9 Group  0 Pid  73333 on {host2} device  1 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 10 Group  0 Pid  73334 on {host2} device  2 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 11 Group  0 Pid  73335 on {host2} device  3 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 12 Group  0 Pid  73336 on {host2} device  4 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 13 Group  0 Pid  73337 on {host2} device  5 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 14 Group  0 Pid  73338 on {host2} device  6 [0x00] NVIDIA A100-SXM4-80GB
#  Rank 15 Group  0 Pid  73339 on {host2} device  7 [0x00] NVIDIA A100-SXM4-80GB
NCCL version 2.12.12+cuda11.6
#
#                                                              out-of-place                       in-place
#       size         count      type   redop    root     time   algbw   busbw #wrong     time   algbw   busbw #wrong
#        (B)    (elements)                               (us)  (GB/s)  (GB/s)            (us)  (GB/s)  (GB/s)
    33554432       8388608     float     sum      -1    650.2   51.61   96.76      0    648.4   51.75   97.03      0
    67108864      16777216     float     sum      -1    956.9   70.13  131.49      0    983.4   68.24  127.96      0
   134217728      33554432     float     sum      -1   1740.3   77.12  144.60      0   1734.2   77.40  145.12      0
   268435456      67108864     float     sum      -1   2966.1   90.50  169.69      0   2929.2   91.64  171.83      0
   536870912     134217728     float     sum      -1   5693.6   94.29  176.80      0   5686.5   94.41  177.02      0
  1073741824     268435456     float     sum      -1    11013   97.50  182.80      0    11099   96.74  181.39      0
# Out of bounds values : 0 OK
# Avg bus bandwidth    : 150.209
#
"""


@pytest.mark.parametrize(
    "critical_threshold, warn_threshold, expected",
    [
        (200, None, ExitCode.OK),
        (200, 210, ExitCode.OK),
        (210, 211, ExitCode.WARN),
        (211, 211, ExitCode.CRITICAL),
    ],
)
def test_check_nccl_successful(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    critical_threshold: float,
    warn_threshold: Optional[float],
    expected: ExitCode,
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(cmd: str, logger: logging.Logger) -> ShellCommandOut:
        return FakeShellCommandOut(
            [],
            0,
            sample_single_success_output.format(hostname=socket.gethostname()),
        )

    args = f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p all_reduce --nccl-tdir /opt/nccl-tests/build/ --critical-threshold {critical_threshold}"
    if warn_threshold is not None:
        args += f" --warn-threshold {warn_threshold}"

    result = runner.invoke(
        check_nccl,
        args,
        obj=mock_shell_command,
    )
    assert result.exit_code == expected.value
    assert "# Avg bus bandwidth    : 210.99" in caplog.text


def test_check_nccl_failure(tmp_path: Path) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(cmd: str, logger: logging.Logger) -> ShellCommandOut:
        return FakeShellCommandOut([], 0, sample_failure_output)

    args = f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p all_reduce --nccl-tdir /opt/nccl-tests/build/ --critical-threshold 200"

    result = runner.invoke(
        check_nccl,
        args,
        obj=mock_shell_command,
    )
    assert result.exit_code == ExitCode.WARN.value


def test_nccl_exception(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    def mock_shell_command(cmd: str, timeout: int) -> ShellCommandOut:
        raise subprocess.CalledProcessError(
            255,
            "",
            "Command returned non-zero exit status 255.",
        )

    runner = CliRunner(mix_stderr=False)
    caplog.at_level(logging.INFO)

    result = runner.invoke(
        check_nccl,
        (
            f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p all_reduce --nccl-tdir /opt/nccl-tests/build/ --critical-threshold 200"
        ),
        obj=mock_shell_command,
    )

    assert result.exit_code == ExitCode.WARN.value
    assert "NCCL Test - all_reduce - FAILED to run." in caplog.text
    assert "Error: Unknown subprocess exception was raised." in caplog.text


@pytest.mark.parametrize(
    "flavor, hostlist, expected_result",
    [
        ("single", None, [(socket.gethostname(),)]),
        ("single", "fairwus3-1-htc-100", [("fairwus3-1-htc-100",)]),
        (
            "single",
            "fairwus3-1-htc-[100-102,115]",
            [
                ("fairwus3-1-htc-100",),
                ("fairwus3-1-htc-101",),
                ("fairwus3-1-htc-102",),
                ("fairwus3-1-htc-115",),
            ],
        ),
        (
            "single",
            "fairwus3-1-htc-100,fairwus3-1-htc-115",
            [
                ("fairwus3-1-htc-100",),
                ("fairwus3-1-htc-115",),
            ],
        ),
        (
            "pairwise",
            "fairwus3-1-htc-[100-101,102]",
            [
                ("fairwus3-1-htc-100", "fairwus3-1-htc-101"),
                ("fairwus3-1-htc-100", "fairwus3-1-htc-102"),
                ("fairwus3-1-htc-101", "fairwus3-1-htc-102"),
            ],
        ),
        (
            "pairwise-quick",
            "fairwus3-1-htc-[100-102]",
            [
                ("fairwus3-1-htc-100", "fairwus3-1-htc-101"),
                ("fairwus3-1-htc-102", "fairwus3-1-htc-100"),
            ],
        ),
    ],
)
def test_get_hosts_success(
    flavor: Flavor,
    hostlist: str,
    expected_result: Any,
) -> None:
    logger = logging.getLogger(__name__)

    result = get_hosts(flavor, hostlist, logger)
    assert result == expected_result


@pytest.mark.parametrize(
    "flavor, hostlist",
    [
        (
            "single",
            "fairwus3-1-htc-100|fairwus3-1-htc-115",
        ),
        ("pairwise", "fairwus3-1-htc-100"),
    ],
)
def test_get_hosts_fail(
    flavor: Flavor,
    hostlist: str,
) -> None:
    logger = logging.getLogger(__name__)

    with pytest.raises(BadParameter):
        get_hosts(flavor, hostlist, logger)


@pytest.mark.parametrize(
    "flavor, hostlist, expected_hosts",
    [
        (
            "pairwise",
            "fairwus3-1-htc-[100-102]",
            [
                ("fairwus3-1-htc-100", "fairwus3-1-htc-101"),
                ("fairwus3-1-htc-100", "fairwus3-1-htc-102"),
                ("fairwus3-1-htc-101", "fairwus3-1-htc-102"),
            ],
        ),
        (
            "pairwise-quick",
            "fairwus3-1-htc-[100-102]",
            [
                ("fairwus3-1-htc-100", "fairwus3-1-htc-101"),
                ("fairwus3-1-htc-102", "fairwus3-1-htc-100"),
            ],
        ),
    ],
)
def test_pairwise_nccl(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    flavor: Flavor,
    hostlist: str,
    expected_hosts: List[Tuple[str, str]],
) -> None:
    runner = CliRunner(mix_stderr=False)

    def mock_shell_command(cmd: str, logger: logging.Logger) -> ShellCommandOut:
        host_arg = re.search("--host (.*?)(?:$|\\s)", cmd)

        host1, host2 = None, None
        if host_arg is not None:
            host1, host2 = [arg.split(":")[0] for arg in host_arg.group(1).split(",")]

        return FakeShellCommandOut(
            [],
            0,
            sample_pairwise_success_output.format(host1=host1, host2=host2),
        )

    args = f"fair_cluster prolog --log-folder={tmp_path} --sink=do_nothing -p all_reduce --{flavor} --hostlist {hostlist} --nccl-tdir /opt/nccl-tests/build/ --critical-threshold 100"

    result = runner.invoke(
        check_nccl,
        args,
        obj=mock_shell_command,
    )

    log_output_messages = []
    for message in caplog.messages:
        if "Output:\n" in message:
            log_output_messages += [message]

    assert len(log_output_messages) == len(expected_hosts)
    for pair, message in zip(expected_hosts, log_output_messages):
        assert message == "Output:\n" + sample_pairwise_success_output.format(
            host1=pair[0], host2=pair[1]
        )

    assert result.exit_code == ExitCode.OK.value
