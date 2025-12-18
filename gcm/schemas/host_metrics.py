# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class HostMetrics:
    max_gpu_util: int
    min_gpu_util: int
    avg_gpu_util: float
    ram_util: float

    @property
    def prefix(self) -> str:
        return "gcm.gpu."
