# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import cast

import pytest

from gcm.accelerator.backend import BackendName, DeviceHandle, ProbeResult
from gcm.accelerator.backends.nvml import NVMLBackend
from gcm.accelerator.errors import (
    BackendOperationError,
    BackendUnavailableError,
    UnsupportedOperationError,
)
from gcm.accelerator.manager import AcceleratorManager
from gcm.accelerator.metrics import MetricRequest
from gcm.accelerator.probe import find_and_load_library
from gcm.accelerator.registry import default_backend_factories
from gcm.monitoring.device_telemetry_client import (
    DeviceTelemetryClient,
    DeviceTelemetryException,
)
from gcm.schemas.gpu.application_clock import ApplicationClockInfo
from gcm.schemas.gpu.memory import GPUMemory
from gcm.schemas.gpu.utilization import GPUUtilization


@dataclass
class _FakeGPUDevice:
    def get_name(self) -> str:
        return "NVIDIA H100"

    def get_vbios_version(self) -> str:
        return "vbios-1.2.3"

    def get_utilization_rates(self) -> GPUUtilization:
        return GPUUtilization(gpu=73, memory=42)

    def get_memory_info(self) -> GPUMemory:
        return GPUMemory(total=1000, free=400, used=600)

    def get_temperature(self) -> int:
        return 67

    def get_power_usage(self) -> int:
        return 250000

    def get_enforced_power_limit(self) -> int:
        return 300000

    def get_clock_freq(self) -> ApplicationClockInfo:
        return ApplicationClockInfo(graphics_freq=1200, memory_freq=1500)

    def get_ecc_corrected_volatile_total(self) -> int:
        return 11

    def get_ecc_uncorrected_volatile_total(self) -> int:
        return 2


class _FakeTelemetryClient:
    def __init__(self) -> None:
        self.closed = False

    def get_device_count(self) -> int:
        return 2

    def get_device_by_index(self, index: int) -> _FakeGPUDevice:
        del index
        return _FakeGPUDevice()

    def close(self) -> None:
        self.closed = True


@dataclass
class _FailingFieldGPUDevice(_FakeGPUDevice):
    def get_temperature(self) -> int:
        raise DeviceTelemetryException()


class _PartialFailureTelemetryClient(_FakeTelemetryClient):
    def get_device_by_index(self, index: int) -> _FailingFieldGPUDevice:
        del index
        return _FailingFieldGPUDevice()


def test_nvml_backend_probe_and_read_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gcm.accelerator.backends.nvml.find_and_load_library",
        lambda names, paths: "/usr/lib/libnvidia-ml.so.1",
    )
    backend = NVMLBackend(
        telemetry_client_factory=lambda: cast(
            DeviceTelemetryClient, _FakeTelemetryClient()
        )
    )

    probe_result = backend.probe()
    assert probe_result.healthy is True
    assert probe_result.library_path == "/usr/lib/libnvidia-ml.so.1"

    devices = backend.enumerate_devices()
    assert len(devices) == 2
    assert devices[0].backend == BackendName.NVML
    assert devices[0].vendor == "nvidia"
    assert devices[0].model == "NVIDIA H100"

    metrics = backend.read_metrics(devices[0], MetricRequest())
    assert metrics.core_util_pct == 73.0
    assert metrics.mem_util_pct == 42.0
    assert metrics.mem_total_bytes == 1000
    assert metrics.mem_used_bytes == 600
    assert metrics.power_w == 250.0
    assert metrics.power_limit_w == 300.0
    assert metrics.sm_clock_mhz == 1200
    assert metrics.mem_clock_mhz == 1500
    assert metrics.ecc_corrected == 11
    assert metrics.ecc_uncorrected == 2


def test_nvml_backend_invalid_device_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gcm.accelerator.backends.nvml.find_and_load_library",
        lambda names, paths: "/usr/lib/libnvidia-ml.so.1",
    )
    backend = NVMLBackend(
        telemetry_client_factory=lambda: cast(
            DeviceTelemetryClient, _FakeTelemetryClient()
        )
    )
    backend.probe()

    with pytest.raises(UnsupportedOperationError):
        backend.read_metrics(
            DeviceHandle(backend=BackendName.NVML, id="not-an-int", vendor="nvidia"),
            MetricRequest(),
        )


def test_nvml_backend_partial_failure_yields_partial_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "gcm.accelerator.backends.nvml.find_and_load_library",
        lambda names, paths: "/usr/lib/libnvidia-ml.so.1",
    )
    backend = NVMLBackend(
        telemetry_client_factory=lambda: cast(
            DeviceTelemetryClient, _PartialFailureTelemetryClient()
        )
    )
    backend.probe()
    device = backend.enumerate_devices()[0]

    metrics = backend.read_metrics(device, MetricRequest())
    assert metrics.core_util_pct == 73.0
    assert metrics.mem_total_bytes == 1000
    # Temperature call fails in fake device, but other fields still map.
    assert metrics.temp_c is None
    assert metrics.power_w == 250.0


def test_nvml_backend_probe_missing_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gcm.accelerator.backends.nvml.find_and_load_library",
        lambda names, paths: None,
    )
    backend = NVMLBackend(
        telemetry_client_factory=lambda: cast(
            DeviceTelemetryClient, _FakeTelemetryClient()
        )
    )
    with pytest.raises(BackendUnavailableError):
        backend.probe()


def test_nvml_backend_close_closes_underlying_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "gcm.accelerator.backends.nvml.find_and_load_library",
        lambda names, paths: "/usr/lib/libnvidia-ml.so.1",
    )
    client = _FakeTelemetryClient()
    backend = NVMLBackend(
        telemetry_client_factory=lambda: cast(DeviceTelemetryClient, client)
    )

    backend.probe()
    backend.close()

    assert client.closed is True


class _FakeBackend:
    def name(self) -> BackendName:
        return BackendName.NVML

    def probe(self) -> ProbeResult:
        return ProbeResult(backend=BackendName.NVML, healthy=True, reason="ok")

    def enumerate_devices(self) -> list[DeviceHandle]:
        return [DeviceHandle(backend=BackendName.NVML, id="0", vendor="nvidia")]

    def capabilities(self, device: DeviceHandle):  # type: ignore[no-untyped-def]
        del device
        return None

    def read_metrics(self, device: DeviceHandle, request: MetricRequest):  # type: ignore[no-untyped-def]
        del device, request
        # Intentionally sparse to validate manager routing only.
        from gcm.accelerator.metrics import MetricSet

        return MetricSet()

    def close(self) -> None:
        return None


def test_manager_probes_refreshes_and_reads() -> None:
    manager = AcceleratorManager(factories={BackendName.NVML: lambda: _FakeBackend()})
    probe_results = manager.probe_all()
    assert probe_results[BackendName.NVML].healthy is True

    manager.refresh_devices()
    devices = manager.devices()
    assert len(devices) == 1
    assert devices[0].id == "0"

    metrics = manager.read_all_metrics(MetricRequest())
    assert "nvml/0" in metrics


class _HealthyBackend(_FakeBackend):
    def __init__(self, backend_name: BackendName = BackendName.NVML) -> None:
        self._backend_name = backend_name
        self.closed = False

    def name(self) -> BackendName:
        return self._backend_name

    def probe(self) -> ProbeResult:
        return ProbeResult(backend=self._backend_name, healthy=True, reason="ok")

    def close(self) -> None:
        self.closed = True


class _UnhealthyBackend(_FakeBackend):
    def __init__(self, backend_name: BackendName = BackendName.NVML) -> None:
        self._backend_name = backend_name
        self.closed = False

    def name(self) -> BackendName:
        return self._backend_name

    def probe(self) -> ProbeResult:
        return ProbeResult(backend=self._backend_name, healthy=False, reason="missing")

    def close(self) -> None:
        self.closed = True


def test_manager_probe_all_unhealthy_backend() -> None:
    unhealthy = _UnhealthyBackend(BackendName.NVML)
    manager = AcceleratorManager(factories={BackendName.NVML: lambda: unhealthy})
    results = manager.probe_all()

    assert results[BackendName.NVML].healthy is False
    assert manager.get_backend(BackendName.NVML) is None
    assert unhealthy.closed is True


def test_manager_reprobe_closes_stale_backend() -> None:
    first_backend = _HealthyBackend()
    second_backend = _HealthyBackend()
    created = [first_backend, second_backend]

    def _factory() -> _HealthyBackend:
        return created.pop(0)

    manager = AcceleratorManager(factories={BackendName.NVML: _factory})
    manager.probe_all()
    assert manager.get_backend(BackendName.NVML) is first_backend
    assert first_backend.closed is False

    manager.probe_all()
    assert first_backend.closed is True
    assert manager.get_backend(BackendName.NVML) is second_backend


class _BrokenEnumerateBackend(_HealthyBackend):
    def enumerate_devices(self) -> list[DeviceHandle]:
        raise RuntimeError("enumerate boom")


def test_manager_wraps_enumerate_errors() -> None:
    manager = AcceleratorManager(
        factories={BackendName.NVML: lambda: _BrokenEnumerateBackend()}
    )
    manager.probe_all()
    with pytest.raises(BackendOperationError):
        manager.refresh_devices()


def test_probe_prefers_discovered_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gcm.accelerator.probe.find_library", lambda _: "libA")

    loaded_paths: list[str] = []

    def _fake_cdll(path: str) -> object:
        loaded_paths.append(path)
        return object()

    monkeypatch.setattr("gcm.accelerator.probe.CDLL", _fake_cdll)
    selected = find_and_load_library(["nvidia-ml"], ["/fallback/libnvidia-ml.so"])
    assert selected == "libA"
    assert loaded_paths == ["libA"]


def test_probe_fallback_when_discovered_library_unloadable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("gcm.accelerator.probe.find_library", lambda _: "libA")

    def _fake_cdll(path: str) -> object:
        if path == "libA":
            raise OSError("bad lib")
        return object()

    monkeypatch.setattr("gcm.accelerator.probe.CDLL", _fake_cdll)
    selected = find_and_load_library(["nvidia-ml"], ["/fallback/libnvidia-ml.so"])
    assert selected == "/fallback/libnvidia-ml.so"


def test_registry_includes_expected_backends() -> None:
    factories = default_backend_factories()
    assert BackendName.NVML in factories
    assert len(factories) == 1
