# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional

from gcm.schemas.device_metrics import DeviceMetrics


@dataclass
class IndexedDeviceMetrics(DeviceMetrics):
    gpu_index: Optional[int] = None

    @property
    def prefix(self) -> str:
        return "gcm.gpu.{}.".format(self.gpu_index)
