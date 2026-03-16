# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""Tests for get_gpu_devices including ROCR_VISIBLE_DEVICES (AMD/ROCm)."""

from unittest.mock import MagicMock

import pytest

from gcm.health_checks.device_telemetry_utils import get_gpu_devices


def test_get_gpu_devices_prolog_slurm_job_gpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """SLURM_JOB_GPUS takes precedence."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_device_count.return_value = 8
    monkeypatch.setenv("SLURM_JOB_GPUS", "0,1,2")
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.delenv("ROCR_VISIBLE_DEVICES", raising=False)
    out = get_gpu_devices(mock_telemetry, "prolog")
    assert out == [0, 1, 2]
    mock_telemetry.get_device_count.assert_not_called()


def test_get_gpu_devices_prolog_rocr_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ROCR_VISIBLE_DEVICES used when SLURM_JOB_GPUS and CUDA_VISIBLE_DEVICES unset."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_device_count.return_value = 4
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setenv("ROCR_VISIBLE_DEVICES", "2,3")
    out = get_gpu_devices(mock_telemetry, "epilog")
    assert out == [2, 3]
    mock_telemetry.get_device_count.assert_not_called()


def test_get_gpu_devices_prolog_cuda_visible_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CUDA_VISIBLE_DEVICES used when SLURM_JOB_GPUS unset."""
    mock_telemetry = MagicMock()
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "1,2,3")
    monkeypatch.delenv("ROCR_VISIBLE_DEVICES", raising=False)
    out = get_gpu_devices(mock_telemetry, "prolog")
    assert out == [1, 2, 3]


def test_get_gpu_devices_nagios_all_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-prolog/epilog returns all device indices."""
    mock_telemetry = MagicMock()
    mock_telemetry.get_device_count.return_value = 4
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.delenv("ROCR_VISIBLE_DEVICES", raising=False)
    out = get_gpu_devices(mock_telemetry, "nagios")
    assert out == [0, 1, 2, 3]
    mock_telemetry.get_device_count.assert_called_once()


def test_get_gpu_devices_prolog_empty_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prolog/epilog with no GPU env vars returns empty list."""
    mock_telemetry = MagicMock()
    monkeypatch.delenv("SLURM_JOB_GPUS", raising=False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.delenv("ROCR_VISIBLE_DEVICES", raising=False)
    out = get_gpu_devices(mock_telemetry, "epilog")
    assert out == []
