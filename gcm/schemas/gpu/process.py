# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class ProcessInfo:
    pid: int
    usedGpuMemory: int  # noqa: N815
