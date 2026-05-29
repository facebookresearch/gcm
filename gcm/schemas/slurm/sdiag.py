# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
from dataclasses import dataclass
from typing import Optional


@dataclass(kw_only=True)
class Sdiag:
    # Populated by the collect site (slurm_monitor.collect_sdiag), not by the
    # `sdiag --json` parser, so the parser path keeps working unmodified.
    cluster: Optional[str] = None

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
    schedule_cycle_last: Optional[int] = None
    schedule_cycle_mean_depth: Optional[int] = None
    schedule_cycle_depth: Optional[int] = None

    # Schedule exit reasons
    schedule_exit_end_job_queue: Optional[int] = None
    schedule_exit_default_queue_depth: Optional[int] = None
    schedule_exit_max_job_start: Optional[int] = None
    schedule_exit_max_rpc_cnt: Optional[int] = None
    schedule_exit_max_sched_time: Optional[int] = None
    schedule_exit_licenses: Optional[int] = None

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
    bf_last_backfilled_jobs: Optional[int] = None
    bf_backfilled_het_jobs: Optional[int] = None
    bf_cycle_counter: Optional[int] = None
    bf_cycle_mean: Optional[int] = None
    bf_cycle_sum: Optional[int] = None
    bf_cycle_max: Optional[int] = None
    bf_cycle_last: Optional[int] = None
    bf_depth_mean: Optional[int] = None
    bf_depth_mean_try: Optional[int] = None
    bf_depth_sum: Optional[int] = None
    bf_depth_try_sum: Optional[int] = None
    bf_last_depth: Optional[int] = None
    bf_last_depth_try: Optional[int] = None
    bf_queue_len: Optional[int] = None
    bf_queue_len_mean: Optional[int] = None
    bf_queue_len_sum: Optional[int] = None
    bf_table_size: Optional[int] = None
    bf_table_size_sum: Optional[int] = None
    bf_table_size_mean: Optional[int] = None
    bf_when_last_cycle: Optional[int] = None
    bf_active: Optional[bool] = None

    # Backfill exit reasons (matches upstream Sdiag schema field names)
    bf_exit_end_job_queue: Optional[int] = None
    bf_exit_max_job_start: Optional[int] = None
    bf_exit_max_job_test: Optional[int] = None
    bf_exit_max_time: Optional[int] = None
    bf_exit_node_space_size: Optional[int] = None
    bf_exit_state_changed: Optional[int] = None

    # Timing
    req_time: Optional[int] = None
    req_time_start: Optional[int] = None
    gettimeofday_latency: Optional[int] = None
    job_states_ts: Optional[int] = None
    parts_packed: Optional[int] = None

    # Raw JSON blobs for complex nested data
    rpcs_by_message_type_json: Optional[str] = None
    rpcs_by_user_json: Optional[str] = None
