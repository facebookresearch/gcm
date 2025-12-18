# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass


@dataclass
class ApplicationClockInfo:
    graphics_freq: int
    memory_freq: int
