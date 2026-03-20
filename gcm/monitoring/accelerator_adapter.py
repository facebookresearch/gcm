# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

from gcm.accelerator.backend import BackendName
from gcm.accelerator.manager import AcceleratorManager
from gcm.monitoring.device_telemetry_client import DeviceTelemetryClient, GPUDevice


class AcceleratorTelemetryAdapter(DeviceTelemetryClient):
    """
    Adapter to allow legacy code expecting DeviceTelemetryClient/GPUDevice
    to function using AcceleratorManager.
    """

    def __init__(self, manager: AcceleratorManager):
        self._manager = manager
        # Ensure we have probed
        self._manager.probe_all()

    def get_device_count(self) -> int:
        backend = self._manager.get_backend(BackendName.NVML)
        # If NVML backend isn't available, count is 0
        if not backend:
            return 0

        # Enumerate to get count.
        return len(backend.enumerate_devices())

    def get_device_by_index(self, index: int) -> GPUDevice:
        backend = self._manager.get_backend(BackendName.NVML)
        if not backend:
            raise IndexError("NVML Backend not available")

        # We need to access get_raw_handle which we added to NVMLBackend
        # We can detect it dynamically
        if hasattr(backend, "get_raw_handle"):
            return backend.get_raw_handle(str(index))  # type: ignore[attr-defined]

        raise NotImplementedError(
            "Backend does not support raw handle access needed for legacy code"
        )
