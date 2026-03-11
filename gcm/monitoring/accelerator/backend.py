# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, List, Protocol

from gcm.monitoring.accelerator.metrics import CapabilitySet, MetricRequest, MetricSet


class BackendName(str, Enum):
    NVML = "nvml"


@dataclass(frozen=True)
class ProbeResult:
    backend: BackendName
    healthy: bool
    reason: str
    library_path: str | None = None
    driver_version: str | None = None
    probed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class DeviceHandle:
    backend: BackendName
    id: str
    vendor: str
    model: str | None = None
    bus_id: str | None = None
    serial: str | None = None


class AcceleratorBackend(Protocol):
    def name(self) -> BackendName: ...

    def probe(self) -> ProbeResult: ...

    def enumerate_devices(self) -> List[DeviceHandle]: ...

    def capabilities(self, device: DeviceHandle) -> CapabilitySet: ...

    def read_metrics(
        self, device: DeviceHandle, request: MetricRequest
    ) -> MetricSet: ...

    def close(self) -> None: ...


BackendFactory = Callable[[], AcceleratorBackend]
