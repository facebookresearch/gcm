# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class SinfoCpusGpus:
    total_cpus_avail: Optional[int]
    total_gpus_avail: Optional[int]
    total_cpus_up: Optional[int]
    total_gpus_up: Optional[int]
    total_cpus_down: Optional[int]
    total_gpus_down: Optional[int]
