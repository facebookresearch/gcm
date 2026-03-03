# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

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
class NeuronBackend(AcceleratorBackend):
    def name(self) -> BackendName:
        return BackendName.NEURON

    def probe(self) -> ProbeResult:
        # Placeholder for AWS Neuron runtime probes.
        raise BackendUnavailableError("Neuron backend not configured for this platform")

    def enumerate_devices(self) -> list[DeviceHandle]:
        raise UnsupportedOperationError("Neuron enumerate_devices not implemented")

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
        raise UnsupportedOperationError("Neuron read_metrics not implemented")

    def close(self) -> None:
        return None
