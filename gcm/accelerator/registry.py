# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.accelerator.backend import BackendFactory, BackendName
from gcm.accelerator.backends.nvml import NVMLBackend


def default_backend_factories() -> dict[BackendName, BackendFactory]:
    return {
        BackendName.NVML: lambda: NVMLBackend(),
    }
