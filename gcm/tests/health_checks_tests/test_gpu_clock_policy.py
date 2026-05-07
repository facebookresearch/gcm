# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from pathlib import Path
from typing import List

from click.testing import CliRunner

from gcm.health_checks.checks.check_nvidia_smi import check_nvidia_smi, NvidiaSmiCli
from gcm.health_checks.types import ExitCode
from gcm.monitoring.device_telemetry_client import ApplicationClockInfo, GPUDevice
from gcm.tests.fakes import FakeGPUDevice


@dataclass
class FakeClockGpuDevice(FakeGPUDevice):
    app_clock_info: ApplicationClockInfo

    def get_clock_freq(self) -> ApplicationClockInfo:
        return self.app_clock_info


@dataclass
class FakeDeviceTelemetryClient:
    app_clock_info: List[ApplicationClockInfo]

    def get_device_count(self) -> int:
        return len(self.app_clock_info)

    def get_device_by_index(self, index: int) -> GPUDevice:
        return FakeClockGpuDevice(self.app_clock_info[index])


@dataclass
class FakeNvidiaSmiCliObject:
    cluster: str
    type: str
    log_level: str
    log_folder: str
    app_clock_info: List[ApplicationClockInfo]

    def get_device_telemetry(self) -> FakeDeviceTelemetryClient:
        return FakeDeviceTelemetryClient(self.app_clock_info)


def test_check_gpu_clock_policy_command_ok(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        [ApplicationClockInfo(graphics_freq=1155, memory_freq=1593)],
    )

    result = runner.invoke(
        check_nvidia_smi,
        (
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_policy "
            "--expected-graphics-freq 1155 "
            "--expected-memory-freq 1593 "
            "--warn-delta-mhz 30 "
            "--critical-delta-mhz 75"
        ),
        obj=fake_obj,
    )

    assert result.exit_code == ExitCode.OK.value


def test_check_gpu_clock_policy_command_warn(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        [ApplicationClockInfo(graphics_freq=1200, memory_freq=1593)],
    )

    result = runner.invoke(
        check_nvidia_smi,
        (
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_policy "
            "--expected-graphics-freq 1155 "
            "--expected-memory-freq 1593 "
            "--warn-delta-mhz 30 "
            "--critical-delta-mhz 75"
        ),
        obj=fake_obj,
    )

    assert result.exit_code == ExitCode.WARN.value


def test_check_gpu_clock_policy_command_critical(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        [ApplicationClockInfo(graphics_freq=1300, memory_freq=1593)],
    )

    result = runner.invoke(
        check_nvidia_smi,
        (
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_policy "
            "--expected-graphics-freq 1155 "
            "--expected-memory-freq 1593 "
            "--warn-delta-mhz 30 "
            "--critical-delta-mhz 75"
        ),
        obj=fake_obj,
    )

    assert result.exit_code == ExitCode.CRITICAL.value


def test_check_gpu_clock_policy_uses_worst_case_across_gpus(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        [
            ApplicationClockInfo(graphics_freq=1155, memory_freq=1593),
            ApplicationClockInfo(graphics_freq=1200, memory_freq=1593),
            ApplicationClockInfo(graphics_freq=1300, memory_freq=1593),
        ],
    )

    result = runner.invoke(
        check_nvidia_smi,
        (
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_policy "
            "--expected-graphics-freq 1155 "
            "--expected-memory-freq 1593 "
            "--warn-delta-mhz 30 "
            "--critical-delta-mhz 75"
        ),
        obj=fake_obj,
    )

    assert result.exit_code == ExitCode.CRITICAL.value


def test_check_gpu_clock_policy_zero_gpu_warn(
    tmp_path: Path,
) -> None:
    runner = CliRunner(mix_stderr=False)

    fake_obj: NvidiaSmiCli = FakeNvidiaSmiCliObject(
        "cluster",
        "type",
        "log_level",
        "log_folder",
        [],
    )

    result = runner.invoke(
        check_nvidia_smi,
        (
            f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c clock_policy "
            "--expected-graphics-freq 1155 "
            "--expected-memory-freq 1593 "
            "--warn-delta-mhz 30 "
            "--critical-delta-mhz 75"
        ),
        obj=fake_obj,
    )

    assert result.exit_code == ExitCode.WARN.value
