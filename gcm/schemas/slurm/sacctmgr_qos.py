# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from typing import Hashable

from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass(kw_only=True)
class SacctmgrQosPayload(DerivedCluster):
    ds: str
    cluster: str
    sacctmgr_qos: dict[Hashable, str]
