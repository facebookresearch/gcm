# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass
class KubernetesNodeConditionRow:
    """Kubernetes node condition schema.

    Fields correspond to node condition data from the Kubernetes API.
    """

    name: str | None = None
    condition_type: str | None = None
    status: str | None = None
    reason: str | None = None
    message: str | None = None


@dataclass(kw_only=True)
class KubernetesNodePayload(DerivedCluster):
    ds: str
    collection_unixtime: int
    cluster: str
    node_condition: KubernetesNodeConditionRow
