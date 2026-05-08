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

    # Schedule exit statistics
    schedule_exit_end_job_queue: Optional[int] = None
    schedule_exit_default_queue_depth: Optional[int] = None
    schedule_exit_max_job_start: Optional[int] = None
    schedule_exit_max_rpc_cnt: Optional[int] = None
    schedule_exit_max_sched_time: Optional[int] = None
    schedule_exit_licenses: Optional[int] = None

    # Backfill exit statistics
    bf_exit_end_job_queue: Optional[int] = None
    bf_exit_max_job_start: Optional[int] = None
    bf_exit_max_job_test: Optional[int] = None
    bf_exit_max_time: Optional[int] = None
    bf_exit_node_space_size: Optional[int] = None
    bf_exit_state_changed: Optional[int] = None
