# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class GPUMemory:
    total: int
    free: int
    used: int
