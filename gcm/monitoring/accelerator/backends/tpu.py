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


@dataclass
class TPUBackend(AcceleratorBackend):
    def name(self) -> BackendName:
        return BackendName.TPU

    def probe(self) -> ProbeResult:
        raise BackendUnavailableError("TPU backend not configured for this platform")

    def enumerate_devices(self) -> list[DeviceHandle]:
        raise UnsupportedOperationError("TPU enumerate_devices not implemented")

    def capabilities(self, device: DeviceHandle) -> CapabilitySet:
        del device
        return CapabilitySet(
            values={
                Capability.UTILIZATION,
                Capability.MEMORY,
                Capability.POWER,
                Capability.THERMALS,
                Capability.CLOCKS,
            }
        )

    def read_metrics(self, device: DeviceHandle, request: MetricRequest) -> MetricSet:
        del device, request
        raise UnsupportedOperationError("TPU read_metrics not implemented")

    def close(self) -> None:
        return None

    def degraded_probe_result(self) -> ProbeResult:
        return ProbeResult(
            backend=self.name(),
            healthy=False,
            reason="TPU probe not configured for this platform",
            probed_at=datetime.now(timezone.utc),
        )
