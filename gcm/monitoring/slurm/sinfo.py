#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
import subprocess
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import tzinfo
from functools import reduce
from typing import Any, DefaultDict, Dict, Generator, Optional

from gcm.monitoring.clock import AwareDatetime, tz_aware_fromisoformat

from gcm.monitoring.slurm.constants import (
    FAILED_JOB_STATES,
    NODE_DOWN_STATES,
    NODE_RUNNING_JOB_STATES,
    NODE_STATES,
    PENDING_JOB_STATES,
    RUNNING_JOB_STATES,
)
from gcm.monitoring.slurm.parsing import extract_gpus_from_gres, parse_gres
from gcm.monitoring.utils import error
from gcm.schemas.slurm.sacct import SacctMetrics
from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_cpus_gpus import SinfoCpusGpus
from gcm.schemas.slurm.sinfo_node_states import SinfoNodeStates
from gcm.schemas.slurm.slurm_log import SLURMLogAccountMetrics


LOGGER_NAME = "slurm.sinfo"
log_error = error.log_error(logger_name=LOGGER_NAME)

logger = logging.getLogger(LOGGER_NAME)


def compute_mean_and_variance(
    jobs: Sequence[Mapping[str, Any]], key: str
) -> tuple[float, float]:
    """Compute the mean & variance of a list of values"""
    jobs = [j for j in jobs if key in j and j[key] is not None]
    num_jobs = len(jobs)
    if num_jobs == 0:
        raise ValueError(
            f"No jobs in given sequence had at least one with the key '{key}'"
        )

    def gen_floatx() -> Generator[float, None, None]:
        yield from (float(j[key]) for j in jobs)

    # Compute the mean
    mean_value = reduce(lambda acc, x: acc + x, gen_floatx(), 0.0)
    mean_value = mean_value / num_jobs

    # Compute the un-biased sample variance
    var_value = reduce(lambda acc, x: acc + (x - mean_value) ** 2, gen_floatx(), 0.0)
    if num_jobs > 1:
        var_value = var_value / (num_jobs - 1)
    else:
        var_value = 0.0

    return (mean_value, var_value)


def compute_resources_pending(jobs: Sequence[SacctMetrics]) -> tuple[int, int, int]:
    """Retrieve the number of jobs, gpus, and nodes waiting/pending."""
    jobs_pending = 0
    gpus_pending = 0
    nodes_pending = 0
    for job in jobs:
        if job.State.lower() in PENDING_JOB_STATES:
            jobs_pending += 1
            gpus_pending += job.ReqGPUS
            nodes_pending += job.ReqNodes
    return jobs_pending, gpus_pending, nodes_pending


@log_error
def compute_failed_jobs(jobs: Sequence[SacctMetrics]) -> int:
    """Retrieve the number of failed jobs."""
    jobs_failed = sum(
        1
        for job in jobs
        if any(job.State.lower().startswith(state) for state in FAILED_JOB_STATES)
    )
    return jobs_failed


@log_error
def compute_running_and_pending_users(jobs: Sequence[SacctMetrics]) -> int:
    """Retrieve the number of unique users with jobs running or pending."""
    unique_users = {
        job.User
        for job in jobs
        if job.State.lower() in PENDING_JOB_STATES
        or job.State.lower() in RUNNING_JOB_STATES
    }
    return len(unique_users)


@log_error
def compute_jobs_without_user(jobs: Sequence[SacctMetrics]) -> int:
    """Retrieve the number of jobs that are running or waiting but do not have a username associated with them.
    This is considered jobs that have a UID attached to them from squeue instead of a username.
    """
    jobs_without_user = sum(1 for job in jobs if job.User.isnumeric())
    return jobs_without_user


def compute_wait_time_distribution(jobs: list[SacctMetrics]) -> tuple[float, float]:
    """Compute the job wait time distribution."""
    # For all jobs, create a waiting time field.
    for index, job in enumerate(jobs):
        try:
            submit_time = tz_aware_fromisoformat(job.Submit)
        except ValueError:
            logger.exception(f"Invalid Submit '{job.Submit=}' for job {job.JobID=}")
            continue
        try:
            start_time = tz_aware_fromisoformat(job.Start)
        except ValueError:
            logger.exception(f"Invalid Start '{job.Start=}' for job {job.JobID=}")
            continue
        wait_time = start_time - submit_time

        jobs[index].WaitingTime = wait_time.total_seconds()

    # Compute the mean and variance.
    return compute_mean_and_variance([asdict(job) for job in jobs], "WaitingTime")


@log_error
def compute_percent_jobs_distributed_training(jobs: Sequence[SacctMetrics]) -> float:
    """Compute the percent of jobs that use more than one node."""
    # Compute the number of jobs using more than a single node
    num_jobs_distributed = 0
    for job in jobs:
        if job.AllocNodes > 1:
            num_jobs_distributed += 1
    # Compute the percentage of jobs using more than one node.
    percent_jobs_distributed = num_jobs_distributed / len(jobs)

    return percent_jobs_distributed


@log_error
def compute_job_runtime_distribution(
    jobs: Sequence[SacctMetrics],
) -> tuple[float, float]:
    """Compute the mean and variance for job run times."""
    # Compute the mean and variance.
    run_mean, run_var = compute_mean_and_variance(
        [asdict(job) for job in jobs], "RunTimeSeconds"
    )

    return run_mean, run_var


@log_error
def compute_distribution_jobs_per_user(
    jobs: Sequence[SacctMetrics],
) -> tuple[float, float]:
    """Compute the mean and variance for # of jobs ran per user."""
    # Create a map from user to number of jobs.
    jobs_per_user: DefaultDict[str, int] = defaultdict(int)
    for job in jobs:
        jobs_per_user[job.User] += 1

    # Transform to list of dicts for the helper method.
    jobs_user_info = []
    for user in jobs_per_user:
        jobs_user_info.append({"NumberJobs": jobs_per_user[user]})

    # Find the mean number of jobs completed per user.
    jobs_per_user_mean, jobs_per_user_variance = compute_mean_and_variance(
        jobs_user_info, "NumberJobs"
    )

    return jobs_per_user_mean, jobs_per_user_variance


@log_error
def compute_avg_time_job_suspended(jobs: Sequence[SacctMetrics]) -> tuple[float, float]:
    # Compute the mean and variance.
    run_mean, run_var = compute_mean_and_variance(
        [asdict(job) for job in jobs], "SuspendedSeconds"
    )

    return run_mean, run_var


@log_error
def compute_number_of_active_users(jobs: Sequence[SacctMetrics]) -> int:
    """Compute the number of active users within the window."""
    active_users = {job.User for job in jobs}

    return len(active_users)


def compute_avg_allocated_cpus_gpus(
    start_time: AwareDatetime,
    end_time: AwareDatetime,
    jobs: Sequence[SacctMetrics],
    system_tz: Optional[tzinfo] = None,
) -> tuple[float, float]:
    """Compute the average number of allocated cpus and gpus per job.
    (weighted by time).
    """
    if end_time <= start_time:
        raise ValueError(f"End time {end_time} must be after start time {start_time}")

    # Apply the weighted by time scheme
    total_time = 0.0
    weighted_cpu_usage = 0.0
    weighted_gpu_usage = 0.0
    for job in jobs:
        try:
            job_start_time = tz_aware_fromisoformat(job.Start, system_tz)
        except ValueError:
            logger.exception(f"Invalid Start '{job.Start=}' for job {job.JobID=}")
            continue
        try:
            job_end_time = tz_aware_fromisoformat(job.End, system_tz)
        except ValueError:
            logger.exception(f"Invalid End '{job.End=}' for job {job.JobID=}")
            continue

        # Truncate portion of job lying outside the window.
        truncate_job_starttime = max(job_start_time, start_time)
        truncate_job_endtime = min(job_end_time, end_time)

        # Compute the total time within the interval.
        secs_within_interval = (
            truncate_job_endtime - truncate_job_starttime
        ).total_seconds()

        # Add the cpu & gpu allocation values, weighted by time.
        weighted_cpu_usage += secs_within_interval * job.AllocCPUS
        weighted_gpu_usage += secs_within_interval * job.AllocGPUS

        # Increment to the total job time.
        total_time += secs_within_interval

    # Compute the weighted average.
    if total_time > 0:
        weighted_cpu_usage = weighted_cpu_usage / total_time
        weighted_gpu_usage = weighted_gpu_usage / total_time

    return (weighted_cpu_usage, weighted_gpu_usage)


def compute_allocated_resources(jobs: Sequence[SacctMetrics]) -> tuple[int, int, int]:
    total_cpus_alloc = 0
    total_gpus_alloc = 0
    total_nodes_alloc = 0
    for job in jobs:
        total_cpus_alloc += job.AllocCPUS
        total_gpus_alloc += job.AllocGPUS
        total_nodes_alloc += job.AllocNodes

    return (total_cpus_alloc, total_gpus_alloc, total_nodes_alloc)


def compute_per_account_slurm_log(
    jobs: Sequence[SacctMetrics], derived_cluster: str
) -> Generator[SLURMLogAccountMetrics, None, None]:
    job_runtime_mean = None
    job_runtime_variance = None
    per_account_jobs = defaultdict(list)
    for job in jobs:
        per_account_jobs[job.Account].append(job)

    for account, jobs in per_account_jobs.items():
        if account == "":
            continue
        job_runtime_distribution = compute_job_runtime_distribution(jobs)
        if job_runtime_distribution:
            job_runtime_mean, job_runtime_variance = job_runtime_distribution
        total_cpus_alloc, total_gpus_alloc, total_nodes_alloc = (
            compute_allocated_resources(jobs)
        )
        log = SLURMLogAccountMetrics(
            prefix=f"gcm.{account}.",
            account=account,
            derived_cluster=derived_cluster,
            total_gpus_alloc=total_gpus_alloc,
            total_cpus_alloc=total_cpus_alloc,
            total_nodes_alloc=total_nodes_alloc,
            job_runtime_mean=job_runtime_mean,
            job_runtime_variance=job_runtime_variance,
            active_users=compute_number_of_active_users(jobs),
            jobs_dist_training_percent=compute_percent_jobs_distributed_training(jobs),
        )
        yield log


def get_slurm_version() -> tuple[int, ...]:
    cmd = ["sinfo", "-V"]
    slurm_version = subprocess.check_output(cmd, text=True, timeout=10)
    version = tuple(int(v) for v in slurm_version.strip().split(" ")[1].split("."))
    return version


@log_error
def compute_down_nodes(sinfo: Sinfo) -> int:
    """Retrieve the number of down nodes."""
    unique_down_nodes = {
        node.name
        for node in sinfo.nodes
        if any(node.state.startswith(s) for s in NODE_DOWN_STATES)
    }
    return len(unique_down_nodes)


@log_error
def compute_total_cpus_gpus(sinfo: Sinfo) -> SinfoCpusGpus:
    """Compute the total number of cpus and gpus used within the cluster."""
    data: Dict[str, int] = {
        "total_cpus_down": 0,
        "total_gpus_down": 0,
        "total_cpus_up": 0,
        "total_gpus_up": 0,
        "total_cpus_avail": 0,
        "total_gpus_avail": 0,
    }

    unique_nodes = {node.name: node for node in sinfo.nodes}

    for node in unique_nodes.values():
        # Correctly format the values.
        total_gpus = extract_gpus_from_gres(node.gres)

        # Compute the available cpus & gpus.
        if any(node.state.startswith(s) for s in NODE_DOWN_STATES):
            # The total number of cpus & gpus that are down.
            data["total_cpus_down"] += node.total_cpus
            data["total_gpus_down"] += total_gpus
        else:
            # The total number of gpus & cpus that are currently up.
            data["total_cpus_up"] += node.total_cpus
            data["total_gpus_up"] += total_gpus

        # Store the total number of cpus & gpus inside the system.
        data["total_cpus_avail"] += node.total_cpus
        data["total_gpus_avail"] += total_gpus

    return SinfoCpusGpus(**data)


def compute_total_allocated_cpus_gpus(sinfo: Sinfo) -> tuple[int, int, int]:
    """Computes the total number of cpus, gpus and nodes allocated."""

    unique_nodes = {node.name: node for node in sinfo.nodes}

    alloc_cpus = 0
    alloc_gpus = 0
    alloc_nodes = 0

    for node in unique_nodes.values():
        # XXX: startswith because "These node states may be followed by a special
        # character to identify state flags associated with the node."
        # https://slurm.schedmd.com/sinfo.html#SECTION_NODE-STATE-CODES
        if any(node.state.startswith(s) for s in NODE_RUNNING_JOB_STATES):
            alloc_cpus += node.alloc_cpus
            alloc_gpus += parse_gres(node.gres_used)
            alloc_nodes += 1

    return alloc_cpus, alloc_gpus, alloc_nodes


def compute_node_states(sinfo: Sinfo) -> SinfoNodeStates:
    """Aggregates the metrics parsed from sinfo

    This tracks separately the nodes that are not responding, and aggregates
    (sums) the other states regardless of their connection status.
    """
    if not sinfo.nodes:
        return SinfoNodeStates()
    sinfo_states = SinfoNodeStates(
        nodes_allocated=0,
        nodes_completing=0,
        nodes_down=0,
        nodes_drained=0,
        nodes_draining=0,
        nodes_fail=0,
        nodes_failing=0,
        nodes_future=0,
        nodes_idle=0,
        nodes_inval=0,
        nodes_maint=0,
        nodes_reboot_issued=0,
        nodes_reboot_requested=0,
        nodes_mixed=0,
        nodes_perfctrs=0,
        nodes_planned=0,
        nodes_power_down=0,
        nodes_powered_down=0,
        nodes_powering_down=0,
        nodes_powering_up=0,
        nodes_reserved=0,
        nodes_unknown=0,
        nodes_not_responding=0,
        nodes_unknown_state=0,
        nodes_total=0,
    )

    unique_nodes = {node.name: node for node in sinfo.nodes}

    for node in unique_nodes.values():
        # per the docs, anything ending in * means currently not responding
        # this is regardless of its state
        if node.state.endswith("*"):
            sinfo_states.nodes_not_responding = (
                sinfo_states.nodes_not_responding or 0
            ) + 1

        # remove any state modifiers, and prefix with nodes.
        state = "nodes_{}".format(node.state.rstrip("*~#!%$@^-"))

        if state[6:] not in NODE_STATES:
            sinfo_states.nodes_unknown_state = (
                sinfo_states.nodes_unknown_state or 0
            ) + 1
        else:
            curr_value = getattr(sinfo_states, state)
            setattr(sinfo_states, state, curr_value + 1)

        # add the count to our node total
        sinfo_states.nodes_total = (sinfo_states.nodes_total or 0) + 1

    return sinfo_states
