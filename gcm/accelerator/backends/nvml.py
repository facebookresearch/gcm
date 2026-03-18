# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from gcm.accelerator.backend import BackendName, DeviceHandle, ProbeResult
from gcm.accelerator.errors import BackendUnavailableError, UnsupportedOperationError
from gcm.accelerator.metrics import MetricRequest, MetricSet
from gcm.accelerator.probe import find_and_load_library
from gcm.monitoring.device_telemetry_client import (
    DeviceTelemetryClient,
    DeviceTelemetryException,
)
from gcm.monitoring.utils.error import safe_call
from gcm.schemas.gpu.application_clock import ApplicationClockInfo

from gcm.schemas.gpu.memory import GPUMemory
from gcm.schemas.gpu.utilization import GPUUtilization

_NAMES = ["nvidia-ml"]
_PATHS = [
    "/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1",
    "/usr/lib64/libnvidia-ml.so.1",
    "/usr/lib/libnvidia-ml.so.1",
]

_T = TypeVar("_T")


def _default_nvml_client_factory() -> DeviceTelemetryClient:
    # Keep the import lazy so this package can still be imported in
    # environments where pynvml is unavailable.
    from gcm.monitoring.device_telemetry_nvml import NVMLDeviceTelemetryClient

    return NVMLDeviceTelemetryClient()


@dataclass
class NVMLBackend:
    telemetry_client_factory: Callable[[], DeviceTelemetryClient] = (
        _default_nvml_client_factory
    )
    _client: Optional[DeviceTelemetryClient] = field(
        default=None, init=False, repr=False
    )
    _handles: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def name(self) -> BackendName:
        return BackendName.NVML

    def _ensure_client(self) -> DeviceTelemetryClient:
        if self._client is None:
            self._client = self.telemetry_client_factory()
        return self._client

    def probe(self) -> ProbeResult:
        path = find_and_load_library(_NAMES, _PATHS)
        if path is None:
            raise BackendUnavailableError("NVML shared library not found")
        client = self._ensure_client()
        try:
            client.get_device_count()
        except DeviceTelemetryException as e:
            raise BackendUnavailableError("NVML initialization failed") from e
        return ProbeResult(
            backend=self.name(),
            healthy=True,
            reason="ready",
            library_path=path,
            probed_at=datetime.now(timezone.utc),
        )

    def enumerate_devices(self) -> list[DeviceHandle]:
        client = self._ensure_client()
        try:
            device_count = client.get_device_count()
            devices: list[DeviceHandle] = []
            for index in range(device_count):
                model: Optional[str] = None

                # Check cache first or fetch handle
                dev_id = str(index)
                if dev_id in self._handles:
                    handle = self._handles[dev_id]
                else:
                    handle = client.get_device_by_index(index)
                    self._handles[dev_id] = handle

                model_getter = getattr(handle, "get_name", None)
                if callable(model_getter):
                    maybe_model = self._safe_call(model_getter)
                    if isinstance(maybe_model, str):
                        model = maybe_model
                devices.append(
                    DeviceHandle(
                        backend=self.name(),
                        id=dev_id,
                        vendor="nvidia",
                        model=model,
                    )
                )
            return devices
        except DeviceTelemetryException as e:
            raise UnsupportedOperationError("NVML enumerate_devices failed") from e

    @staticmethod
    def _safe_call(func: Callable[[], _T]) -> _T | None:
        return safe_call(func, DeviceTelemetryException, logger_name=__name__)

    def read_metrics(self, device: DeviceHandle, _request: MetricRequest) -> MetricSet:
        # TODO: Wire MetricRequest.include_process_info once process telemetry
        # is available through HAL MetricSet.
        client = self._ensure_client()
        try:
            if device.id in self._handles:
                handle = self._handles[device.id]
            else:
                index = int(device.id)
                handle = client.get_device_by_index(index)
                self._handles[device.id] = handle
        except (ValueError, DeviceTelemetryException) as e:
            raise UnsupportedOperationError(
                f"invalid NVML device id: {device.id}"
            ) from e

        utilization: GPUUtilization | None = self._safe_call(
            handle.get_utilization_rates
        )
        memory: GPUMemory | None = self._safe_call(handle.get_memory_info)
        temperature: int | None = self._safe_call(handle.get_temperature)
        power_usage: int | None = self._safe_call(handle.get_power_usage)
        power_limit: int | None = self._safe_call(handle.get_enforced_power_limit)
        clocks: ApplicationClockInfo | None = self._safe_call(handle.get_clock_freq)
        ecc_corrected: int | None = self._safe_call(
            handle.get_ecc_corrected_volatile_total
        )
        ecc_uncorrected: int | None = self._safe_call(
            handle.get_ecc_uncorrected_volatile_total
        )

        return MetricSet(
            timestamp=datetime.now(timezone.utc),
            core_util_pct=(float(utilization.gpu) if utilization is not None else None),
            mem_util_pct=(
                float(utilization.memory) if utilization is not None else None
            ),
            mem_total_bytes=(int(memory.total) if memory is not None else None),
            mem_used_bytes=(int(memory.used) if memory is not None else None),
            temp_c=(float(temperature) if temperature is not None else None),
            power_w=(float(power_usage) / 1000.0 if power_usage is not None else None),
            power_limit_w=(
                float(power_limit) / 1000.0 if power_limit is not None else None
            ),
            sm_clock_mhz=(int(clocks.graphics_freq) if clocks is not None else None),
            mem_clock_mhz=(int(clocks.memory_freq) if clocks is not None else None),
            ecc_corrected=(int(ecc_corrected) if ecc_corrected is not None else None),
            ecc_uncorrected=(
                int(ecc_uncorrected) if ecc_uncorrected is not None else None
            ),
        )

    def close(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return None

        close_method = getattr(client, "close", None)
        if callable(close_method):
            close_method()
        return None
