# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for ROCm device telemetry client."""

import json
from unittest.mock import patch

import pytest

from gcm.monitoring.device_telemetry_client import DeviceTelemetryException
from gcm.monitoring.device_telemetry_rocm import (
    ROCmDeviceTelemetryClient,
    ROCmGPUDevice,
    _run_cmd,
)


def test_rocm_client_no_tool_raises() -> None:
    """ROCmDeviceTelemetryClient raises when no amd-smi/rocm-smi on PATH."""
    with patch(
        "gcm.monitoring.device_telemetry_rocm._find_rocm_tool",
        return_value=None,
    ):
        client = ROCmDeviceTelemetryClient(tool_path=None)
        with pytest.raises(DeviceTelemetryException) as exc_info:
            client.get_device_count()
        assert "No ROCm tool found" in str(exc_info.value)


def test_rocm_client_amd_smi_list_json() -> None:
    """ROCmDeviceTelemetryClient uses amd-smi list --json for device count."""
    list_out = json.dumps({"gpus": [{"gpu_id": 0}, {"gpu_id": 1}]})
    with patch(
        "gcm.monitoring.device_telemetry_rocm._find_rocm_tool",
        return_value="amd-smi",
    ), patch(
        "gcm.monitoring.device_telemetry_rocm._run_cmd",
        return_value=list_out,
    ) as run_cmd:
        client = ROCmDeviceTelemetryClient(tool_path="amd-smi")
        count = client.get_device_count()
        assert count == 2
        run_cmd.assert_any_call(["amd-smi", "list", "--json"], 30)


def test_rocm_gpu_device_defaults() -> None:
    """ROCmGPUDevice returns safe defaults for ECC/retired/row_remap."""
    dev = ROCmGPUDevice(0, {}, {}, [])
    assert list(dev.get_retired_pages_double_bit_ecc_error()) == []
    assert list(dev.get_retired_pages_multiple_single_bit_ecc_errors()) == []
    assert dev.get_retired_pages_pending_status() == 0
    remap = dev.get_remapped_rows()
    assert remap.pending == 0 and remap.failure == 0
    assert dev.get_ecc_uncorrected_volatile_total() == 0
    assert dev.get_ecc_corrected_volatile_total() == 0
    assert "AMD" in dev.get_vbios_version() or dev.get_vbios_version() == "AMD-ROCm"


def test_rocm_gpu_device_memory_util() -> None:
    """ROCmGPUDevice maps metrics to memory and utilization."""
    metrics = {
        "average_gfx_activity": 0.5,
        "average_umc_activity": 0.3,
        "temperature_hotspot": 72,
        "current_gfxclk": 1800,
        "current_uclk": 800,
    }
    memory = {"total": 32 * 1024, "free": 16 * 1024, "used": 16 * 1024}  # MB
    dev = ROCmGPUDevice(0, metrics, memory, [])
    mem = dev.get_memory_info()
    assert mem.total >= mem.used
    assert mem.used == mem.total - mem.free
    util = dev.get_utilization_rates()
    assert util.gpu == 50
    assert util.memory == 30
    assert dev.get_temperature() == 72
    clock = dev.get_clock_freq()
    assert clock.graphics_freq == 1800
    assert clock.memory_freq == 800


def test_run_cmd_timeout() -> None:
    """_run_cmd raises DeviceTelemetryException on timeout."""
    import subprocess
    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired("amd-smi", 30),
    ):
        with pytest.raises(DeviceTelemetryException) as exc_info:
            _run_cmd(["amd-smi", "list", "--json"], timeout_secs=30)
        assert "timed out" in str(exc_info.value).lower()


def test_run_cmd_not_found() -> None:
    """_run_cmd raises DeviceTelemetryException when tool not found."""
    with patch(
        "subprocess.run",
        side_effect=FileNotFoundError("amd-smi not found"),
    ):
        with pytest.raises(DeviceTelemetryException) as exc_info:
            _run_cmd(["amd-smi", "list", "--json"])
        assert "not found" in str(exc_info.value).lower()
