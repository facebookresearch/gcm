# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional

from gcm.schemas.slurm.derived_cluster import DerivedCluster
from gcm.schemas.slurm.sdiag import Sdiag
from gcm.schemas.slurm.sinfo_cpus_gpus import SinfoCpusGpus
from gcm.schemas.slurm.sinfo_node_states import SinfoNodeStates


@dataclass(kw_only=True)
class SLURMLogAccountMetrics(DerivedCluster):
    prefix: str
    account: str
    total_gpus_alloc: int
    total_cpus_alloc: int
    total_nodes_alloc: int
    job_runtime_mean: Optional[float]
    job_runtime_variance: Optional[float]
    active_users: Optional[int]
    jobs_dist_training_percent: Optional[float]


@dataclass(kw_only=True)
class SLURMLog(SinfoCpusGpus, SinfoNodeStates, Sdiag, DerivedCluster):
    cluster: str
    active_users: Optional[int]
    running_and_pending_users: Optional[int]
    runaway_jobs: Optional[int]
    avg_cpus_alloc_per_job: Optional[float]
    avg_gpus_alloc_per_job: Optional[float]
    jobs_per_user_mean: Optional[float]
    jobs_per_user_variance: Optional[float]
    job_runtime_mean: Optional[float]
    job_runtime_variance: Optional[float]
    job_suspended_mean: Optional[float]
    job_suspended_variance: Optional[float]
    job_wait_time_mean: Optional[float]
    job_wait_time_variance: Optional[float]
    jobs_dist_training_percent: Optional[float]
    jobs_pending: Optional[int]
    gpus_pending: Optional[int]
    nodes_pending: Optional[int]
    jobs_failed: Optional[int]
    jobs_running: Optional[int]
    jobs_without_user: Optional[int]
    total_cpus_alloc: int
    total_down_nodes: Optional[int]
    total_gpus_alloc: int
    total_nodes_alloc: int
