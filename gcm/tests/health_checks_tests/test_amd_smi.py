# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for AMD SMI health check (check_amd_smi)."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from click.testing import CliRunner

from gcm.health_checks.checks.check_amd_smi import AmdSmiCli, check_amd_smi
from gcm.health_checks.types import ExitCode
from gcm.monitoring.device_telemetry_client import DeviceTelemetryClient, GPUDevice
from gcm.tests.fakes import FakeGPUDevice


@dataclass
class FakeAmdSmiCliObject:
    cluster: str
    type: str
    log_level: str
    log_folder: str
    device_telemetry_client: DeviceTelemetryClient

    def get_device_telemetry(self) -> DeviceTelemetryClient:
        return self.device_telemetry_client


def test_check_amd_smi_gpu_num_ok(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """check_amd_smi gpu_num passes when device count matches expected."""
    class FakeDeviceTelemetryClient:
        devices: list = field(default_factory=lambda: [FakeGPUDevice()] * 8)

        def get_device_count(self) -> int:
            return 8

        def get_device_by_index(self, index: int) -> GPUDevice:
            return self.devices[index]

    fake_obj: AmdSmiCli = FakeAmdSmiCliObject(
        "cluster", "type", "log_level", str(tmp_path), FakeDeviceTelemetryClient()
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_amd_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_num --gpu_num=8",
        obj=fake_obj,
    )
    assert result.exit_code == ExitCode.OK.value
    assert "Number of GPUs present is the same as expected, 8" in caplog.text


def test_check_amd_smi_gpu_num_critical(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """check_amd_smi gpu_num fails when device count does not match."""
    class FakeDeviceTelemetryClient:
        def get_device_count(self) -> int:
            return 4

        def get_device_by_index(self, index: int) -> GPUDevice:
            return FakeGPUDevice()

    fake_obj: AmdSmiCli = FakeAmdSmiCliObject(
        "cluster", "type", "log_level", str(tmp_path), FakeDeviceTelemetryClient()
    )
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        check_amd_smi,
        f"fair_cluster nagios --log-folder={tmp_path} --sink=do_nothing -c gpu_num --gpu_num=8",
        obj=fake_obj,
    )
    assert result.exit_code == ExitCode.CRITICAL.value
    assert "Number of GPUs present, 4, is different than expected, 8" in caplog.text
