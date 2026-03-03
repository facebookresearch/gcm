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

_NAMES = ["ze_loader"]
_PATHS = [
    "/usr/lib/x86_64-linux-gnu/libze_loader.so.1",
    "/usr/lib64/libze_loader.so.1",
    "/usr/lib/libze_loader.so.1",
]


@dataclass
class LevelZeroBackend(AcceleratorBackend):
    def name(self) -> BackendName:
        return BackendName.LEVEL_ZERO

    def probe(self) -> ProbeResult:
        path = find_and_load_library(_NAMES, _PATHS)
        if path is None:
            raise BackendUnavailableError("Level Zero shared library not found")
        return ProbeResult(
            backend=self.name(),
            healthy=True,
            reason="ready",
            library_path=path,
            probed_at=datetime.now(timezone.utc),
        )

    def enumerate_devices(self) -> list[DeviceHandle]:
        raise UnsupportedOperationError("Level Zero enumerate_devices not implemented")

    def capabilities(self, device: DeviceHandle) -> CapabilitySet:
        del device
        return CapabilitySet(
            values={
                Capability.UTILIZATION,
                Capability.MEMORY,
                Capability.POWER,
                Capability.THERMALS,
                Capability.CLOCKS,
                Capability.TOPOLOGY,
                Capability.PROCESSES,
            }
        )

    def read_metrics(self, device: DeviceHandle, request: MetricRequest) -> MetricSet:
        del device, request
        raise UnsupportedOperationError("Level Zero read_metrics not implemented")

    def close(self) -> None:
        return None
