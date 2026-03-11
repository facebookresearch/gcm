# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.monitoring.accelerator.backend import BackendFactory, BackendName
from gcm.monitoring.accelerator.backends.nvml import NVMLBackend


def default_backend_factories() -> dict[BackendName, BackendFactory]:
    return {
        BackendName.NVML: NVMLBackend,
    }
