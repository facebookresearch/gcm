# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from datetime import datetime, timezone

from gcm.monitoring.accelerator.backend import (
    AcceleratorBackend,
    BackendName,
    DeviceHandle,
    ProbeResult,
)
from gcm.monitoring.accelerator.errors import (
    BackendUnavailableError,
    UnsupportedOperationError,
)
from gcm.monitoring.accelerator.metrics import (
    Capability,
    CapabilitySet,
    MetricRequest,
    MetricSet,
)
from gcm.monitoring.accelerator.probe import find_and_load_library

_NAMES = ["rocm_smi64"]
_PATHS = [
    "/opt/rocm/lib/librocm_smi64.so",
    "/usr/lib/librocm_smi64.so",
]


@dataclass
class ROCmBackend(AcceleratorBackend):
    def name(self) -> BackendName:
        return BackendName.ROCM_SMI

    def probe(self) -> ProbeResult:
        path = find_and_load_library(_NAMES, _PATHS)
        if path is None:
            raise BackendUnavailableError("ROCm SMI shared library not found")
        return ProbeResult(
            backend=self.name(),
            healthy=True,
            reason="ready",
            library_path=path,
            probed_at=datetime.now(timezone.utc),
        )

    def enumerate_devices(self) -> list[DeviceHandle]:
        raise UnsupportedOperationError("ROCm enumerate_devices not implemented")

    def capabilities(self, device: DeviceHandle) -> CapabilitySet:
        del device
        return CapabilitySet(
            values={
                Capability.UTILIZATION,
                Capability.MEMORY,
                Capability.POWER,
                Capability.THERMALS,
                Capability.CLOCKS,
                Capability.PROCESSES,
            }
        )

    def read_metrics(self, device: DeviceHandle, request: MetricRequest) -> MetricSet:
        del device, request
        raise UnsupportedOperationError("ROCm read_metrics not implemented")

    def close(self) -> None:
        return None
