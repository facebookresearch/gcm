# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from gcm.monitoring.accelerator.backend import BackendFactory, BackendName
from gcm.monitoring.accelerator.backends.levelzero import LevelZeroBackend
from gcm.monitoring.accelerator.backends.nvml import NVMLBackend
from gcm.monitoring.accelerator.backends.rocm import ROCmBackend
from gcm.monitoring.accelerator.backends.tpu import TPUBackend


def default_backend_factories() -> dict[BackendName, BackendFactory]:
    return {
        BackendName.NVML: NVMLBackend,
        BackendName.ROCM_SMI: ROCmBackend,
        BackendName.LEVEL_ZERO: LevelZeroBackend,
        BackendName.TPU: TPUBackend,
    }
