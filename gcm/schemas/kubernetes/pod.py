# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass

from gcm.schemas.slurm.derived_cluster import DerivedCluster


@dataclass
class KubernetesPodRow:
    """Kubernetes pod status schema.

    Fields correspond to pod metadata and container status from the Kubernetes API.
    """

    name: str | None = None
    namespace: str | None = None
    node_name: str | None = None
    phase: str | None = None
    restart_count: int | None = None
    container_name: str | None = None
    slurm_job_id: str | None = None


@dataclass(kw_only=True)
class KubernetesPodPayload(DerivedCluster):
    ds: str
    collection_unixtime: int
    cluster: str
    pod: KubernetesPodRow
