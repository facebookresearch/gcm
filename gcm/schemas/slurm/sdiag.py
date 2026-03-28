# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class Sdiag:
    server_thread_count: Optional[int]
    agent_queue_size: Optional[int]
    agent_count: Optional[int]
    agent_thread_count: Optional[int]
    dbd_agent_queue_size: Optional[int]

    # Schedule cycle statistics
    schedule_cycle_max: Optional[int] = None
    schedule_cycle_mean: Optional[int] = None
    schedule_cycle_sum: Optional[int] = None
    schedule_cycle_total: Optional[int] = None
    schedule_cycle_per_minute: Optional[int] = None
    schedule_queue_length: Optional[int] = None

    # Job statistics (prefixed with sdiag_ to avoid collision with SLURMLog)
    sdiag_jobs_submitted: Optional[int] = None
    sdiag_jobs_started: Optional[int] = None
    sdiag_jobs_completed: Optional[int] = None
    sdiag_jobs_canceled: Optional[int] = None
    sdiag_jobs_failed: Optional[int] = None
    sdiag_jobs_pending: Optional[int] = None
    sdiag_jobs_running: Optional[int] = None

    # Backfill statistics
    bf_backfilled_jobs: Optional[int] = None
    bf_cycle_mean: Optional[int] = None
    bf_cycle_sum: Optional[int] = None
    bf_cycle_max: Optional[int] = None
    bf_queue_len: Optional[int] = None
