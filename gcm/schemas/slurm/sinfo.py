# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Iterable

from gcm.schemas.slurm.sinfo_node import SinfoNode


@dataclass
class Sinfo:
    nodes: Iterable[SinfoNode]
