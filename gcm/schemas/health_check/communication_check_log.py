# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
"""AMD communication-check telemetry schema (RCCL, MORI).

Used only by check_rccl and check_mori. Nvidia path (check_nccl) continues
to use HealthCheckLog; this schema is not referenced by any Nvidia code.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class CommunicationCheckLog:
    """Telemetry record for AMD communication checks (RCCL, MORI) with optional metrics."""

    # Base fields (same as HealthCheckLog for sink compatibility)
    node: Optional[str]
    gpu_node_id: Optional[str]
    cluster: Optional[str]
    derived_cluster: Optional[str]
    health_check: Optional[str]
    type: Optional[str]
    result: Optional[int]
    _msg: Optional[str]
    job_id: Optional[int]
    start_time: Optional[float]
    end_time: Optional[float]

    # Optional communication metrics (AMD RCCL / MORI)
    bandwidth_gbps: Optional[float] = None
    latency_us: Optional[float] = None
    dispatch_bw_gbps: Optional[float] = None
    combine_bw_gbps: Optional[float] = None
    extra_metrics: Optional[Dict[str, float]] = None
