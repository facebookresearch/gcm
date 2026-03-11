# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.monitoring.accelerator.backend import (
    AcceleratorBackend,
    BackendFactory,
    BackendName,
    DeviceHandle,
    ProbeResult,
)
from gcm.monitoring.accelerator.errors import BackendOperationError
from gcm.monitoring.accelerator.metrics import MetricRequest, MetricSet


class AcceleratorManager:
    def __init__(self, factories: dict[BackendName, BackendFactory]) -> None:
        self._factories = dict(factories)
        self._backends: dict[BackendName, AcceleratorBackend] = {}
        self._devices: dict[str, DeviceHandle] = {}

    def probe_all(self) -> dict[BackendName, ProbeResult]:
        # Reset previously active backends so reprobe can refresh state.
        self.close()
        results: dict[BackendName, ProbeResult] = {}
        for name, factory in self._factories.items():
            backend = factory()
            try:
                result = backend.probe()
            except Exception as e:
                results[name] = ProbeResult(backend=name, healthy=False, reason=str(e))
                backend.close()
                continue

            results[name] = result
            if result.healthy:
                self._backends[name] = backend
            else:
                backend.close()
        return results

    def refresh_devices(self) -> None:
        next_devices: dict[str, DeviceHandle] = {}
        for name, backend in self._backends.items():
            try:
                devices = backend.enumerate_devices()
            except Exception as e:
                raise BackendOperationError(
                    backend=name,
                    operation="enumerate_devices",
                ) from e
            for device in devices:
                key = f"{device.backend.value}/{device.id}"
                next_devices[key] = device
        self._devices = next_devices

    def devices(self) -> list[DeviceHandle]:
        return list(self._devices.values())

    def get_backend(self, name: BackendName) -> AcceleratorBackend | None:
        return self._backends.get(name)

    def read_all_metrics(self, request: MetricRequest) -> dict[str, MetricSet]:
        results: dict[str, MetricSet] = {}
        for key, device in self._devices.items():
            backend = self._backends.get(device.backend)
            if backend is None:
                continue
            try:
                results[key] = backend.read_metrics(device, request)
            except Exception as e:
                raise BackendOperationError(
                    backend=device.backend,
                    operation="read_metrics",
                ) from e
        return results

    def close(self) -> None:
        for backend in self._backends.values():
            backend.close()
        self._backends = {}
        self._devices = {}
