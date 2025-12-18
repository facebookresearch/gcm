# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class GPUUtilization:
    gpu: int
    memory: int
