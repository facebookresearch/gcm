# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import os
from typing import List

from gcm.health_checks.types import CHECK_TYPE

from gcm.monitoring.device_telemetry_client import DeviceTelemetryClient


def get_gpu_devices(
    device_telemetry: DeviceTelemetryClient, type: CHECK_TYPE
) -> List[int]:
    """Get the list of GPU devices. If the type is prolog/epilog only get
    the GPU devices that the user has been allocated."""

    if type == "prolog" or type == "epilog":
        devices_env = os.getenv("SLURM_JOB_GPUS") or os.getenv("CUDA_VISIBLE_DEVICES")
        if not devices_env:
            return []
        else:
            return [int(device) for device in devices_env.split(",")]
    else:
        device_count = device_telemetry.get_device_count()
        return list(range(device_count))
