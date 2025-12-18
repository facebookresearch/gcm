# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass
class DerivedCluster:
    derived_cluster: Optional[str] = None
