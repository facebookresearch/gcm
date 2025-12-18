#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import timedelta
from typing import (
    Collection,
    Generator,
    Literal,
    Mapping,
    Optional,
    Protocol,
    runtime_checkable,
)

import click
import clusterscope
from gcm.exporters import registry
from gcm.monitoring.click import (
    chunk_size_option,
    click_default_cmd,
    cluster_option,
    dry_run_option,
    heterogeneous_cluster_v1_option,
    interval_option,
    log_folder_option,
    log_level_option,
    once_option,
    retries_option,
    sink_option,
    sink_opts_option,
    stdout_option,
)

from gcm.monitoring.clock import (
    AwareDatetime,
    Clock,
    ClockImpl,
    unixtime_to_pacific_datetime,
)
from gcm.monitoring.sink.protocol import DataType, SinkAdditionalParams, SinkImpl
from gcm.monitoring.sink.utils import Factory, HasRegistry
from gcm.monitoring.slurm.client import SlurmCliClient
from gcm.monitoring.slurm.constants import RUNNING_JOB_STATES
from gcm.monitoring.slurm.derived_cluster import get_derived_cluster
from gcm.monitoring.slurm.sacct import parse_slurm_jobs
from gcm.monitoring.slurm.sinfo import (
    compute_avg_allocated_cpus_gpus,
    compute_avg_time_job_suspended,
    compute_distribution_jobs_per_user,
    compute_down_nodes,
    compute_failed_jobs,
    compute_job_runtime_distribution,
    compute_jobs_without_user,
    compute_node_states,
    compute_number_of_active_users,
    compute_per_account_slurm_log,
    compute_percent_jobs_distributed_training,
    compute_resources_pending,
    compute_running_and_pending_users,
    compute_total_allocated_cpus_gpus,
    compute_total_cpus_gpus,
    compute_wait_time_distribution,
)
from gcm.monitoring.utils.monitor import run_data_collection_loop
from gcm.schemas.slurm.sdiag import Sdiag
from gcm.schemas.slurm.sinfo import Sinfo
from gcm.schemas.slurm.sinfo_cpus_gpus import SinfoCpusGpus
from gcm.schemas.slurm.sinfo_node import SinfoNode
from gcm.schemas.slurm.slurm_log import SLURMLog, SLURMLogAccountMetrics
from typeguard import typechecked

LOGGER_NAME = __name__
logger: logging.Logger  # initialization in main()


def get_slurm_log(
    sinfo: Sinfo,
    sdiag: Sdiag,
    start_time: AwareDatetime,
    end_time: AwareDatetime,
    cluster: str,
    derived_cluster: str,
    logger: logging.Logger,
    partition: Optional[str] = None,
) -> Generator[SLURMLog | SLURMLogAccountMetrics, None, None]:
    active_users = None
    running_and_pending_users = None
    jobs_dist_training_percent = None
    job_runtime_mean = None
    job_runtime_variance = None
    jobs_per_user_mean = None
    jobs_per_user_variance = None
    job_suspended_mean = None
    job_suspended_variance = None
    avg_cpus_alloc_per_job = None
    avg_gpus_alloc_per_job = None
    job_wait_time_mean = None
    job_wait_time_variance = None
    jobs_pending = None
    gpus_pending = None
    node_pending = None
    jobs_failed = None
    jobs_running = None
    jobs_without_user = None

    # TODO(T158094822): Re-enable once `cluster_monitor` has fair cluster access
    # runaway_jobs = slurm_client.count_runaway_jobs()
    runaway_jobs = None

    total_down_nodes = compute_down_nodes(sinfo)
    node_states = compute_node_states(sinfo)
    total_cpus_gpus = compute_total_cpus_gpus(sinfo)
    if not total_cpus_gpus:
        total_cpus_gpus = SinfoCpusGpus(
            total_cpus_avail=None,
            total_gpus_avail=None,
            total_cpus_up=None,
            total_gpus_up=None,
            total_cpus_down=None,
            total_gpus_down=None,
        )

    (
        total_cpus_alloc,
        total_gpus_alloc,
        total_nodes_alloc,
    ) = compute_total_allocated_cpus_gpus(sinfo)

    jobs = parse_slurm_jobs(
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        partition=partition,
        logger=logger,
    )

    if jobs:
        # Evaluate the jobs that are pending or failed before only considering those that are running
        try:
            (
                jobs_pending,
                gpus_pending,
                node_pending,
            ) = compute_resources_pending(jobs)
        except Exception:
            logger.exception("Failed to compute the number of resources pending")

        try:
            jobs_failed = compute_failed_jobs(jobs)
        except Exception:
            logger.exception("Failed to compute the number of failed jobs")

        try:
            jobs_without_user = compute_jobs_without_user(jobs)
        except Exception:
            logger.exception("Failed to compute the number of jobs without a user")

        try:
            running_and_pending_users = compute_running_and_pending_users(jobs)
        except Exception:
            logger.exception("Failed to compute the number of unique users")

        # Now only look at jobs that are running.
        jobs = [job for job in jobs if job.State.lower() in RUNNING_JOB_STATES]
        jobs_running = len(jobs)
        if jobs_running > 0:
            yield from compute_per_account_slurm_log(jobs, derived_cluster)
            try:
                (
                    avg_cpus_alloc_per_job,
                    avg_gpus_alloc_per_job,
                ) = compute_avg_allocated_cpus_gpus(
                    start_time,
                    end_time,
                    jobs,
                )
            except Exception:
                logger.exception(
                    "Failed to compute the average number of allocated cpus and gpus per job"
                )

            try:
                job_wait_time_mean, job_wait_time_variance = (
                    compute_wait_time_distribution(jobs)
                )
            except Exception:
                logger.exception("Failed to compute the job wait time distribution")

            active_users = compute_number_of_active_users(jobs)
            jobs_dist_training_percent = compute_percent_jobs_distributed_training(jobs)
            job_runtime_distribution = compute_job_runtime_distribution(jobs)
            distribution_jobs_per_user = compute_distribution_jobs_per_user(jobs)
            avg_time_job_suspended = compute_avg_time_job_suspended(jobs)

            if job_runtime_distribution:
                job_runtime_mean, job_runtime_variance = job_runtime_distribution
            if distribution_jobs_per_user:
                jobs_per_user_mean, jobs_per_user_variance = distribution_jobs_per_user
            if avg_time_job_suspended:
                job_suspended_mean, job_suspended_variance = avg_time_job_suspended

    slurm_log = SLURMLog(
        cluster=cluster,
        derived_cluster=derived_cluster,
        active_users=active_users,
        running_and_pending_users=running_and_pending_users,
        runaway_jobs=runaway_jobs,
        avg_cpus_alloc_per_job=avg_cpus_alloc_per_job,
        avg_gpus_alloc_per_job=avg_gpus_alloc_per_job,
        jobs_per_user_mean=jobs_per_user_mean,
        jobs_per_user_variance=jobs_per_user_variance,
        job_runtime_mean=job_runtime_mean,
        job_runtime_variance=job_runtime_variance,
        job_suspended_mean=job_suspended_mean,
        job_suspended_variance=job_suspended_variance,
        job_wait_time_mean=job_wait_time_mean,
        job_wait_time_variance=job_wait_time_variance,
        jobs_pending=jobs_pending,
        gpus_pending=gpus_pending,
        nodes_pending=node_pending,
        jobs_failed=jobs_failed,
        jobs_running=jobs_running,
        jobs_without_user=jobs_without_user,
        jobs_dist_training_percent=jobs_dist_training_percent,
        total_cpus_alloc=total_cpus_alloc,
        total_gpus_alloc=total_gpus_alloc,
        total_nodes_alloc=total_nodes_alloc,
        total_down_nodes=total_down_nodes,
        **asdict(total_cpus_gpus),
        **asdict(node_states),
        **asdict(sdiag),
    )
    yield slurm_log


@runtime_checkable
class CliObject(HasRegistry[SinkImpl], Protocol):
    @property
    def clock(self) -> Clock: ...

    def cluster(self) -> str: ...


@dataclass
class CliObjectImpl:
    clock: Clock = field(default_factory=ClockImpl)
    registry: Mapping[str, Factory[SinkImpl]] = field(default_factory=lambda: registry)

    def cluster(self) -> str:
        return clusterscope.cluster()


_default_obj: CliObject = CliObjectImpl()


def collect_slurm(
    obj: CliObject,
    interval: int,
    cluster: str,
    logger: logging.Logger,
    heterogeneous_cluster_v1: bool,
) -> Generator[SLURMLog | SLURMLogAccountMetrics, None, None]:
    """Collect all the relevant slurm metrics that will be stored on ODS"""
    end_time = unixtime_to_pacific_datetime(obj.clock.unixtime())
    start_time = end_time - timedelta(seconds=interval)
    slurm_client = SlurmCliClient()

    sinfo = slurm_client.sinfo_structured()
    sdiag = slurm_client.sdiag_structured()

    if heterogeneous_cluster_v1:
        nodes_per_partition: dict[str, list[SinfoNode]] = defaultdict(list)
        for node in sinfo.nodes:
            nodes_per_partition[node.partition].append(node)

        for partition, nodes in nodes_per_partition.items():
            # empty partition is used for cluster wide metrics
            if partition == "":
                continue

            derived_cluster = get_derived_cluster(
                data={"Partition": partition},
                heterogeneous_cluster_v1=heterogeneous_cluster_v1,
                cluster=cluster,
            )
            slurm_log = get_slurm_log(
                sinfo=Sinfo(nodes=nodes),
                sdiag=sdiag,
                start_time=start_time,
                end_time=end_time,
                cluster=cluster,
                derived_cluster=derived_cluster,
                logger=logger,
                partition=partition,
            )
            yield from slurm_log
    # always yield cluster wide metrics
    slurm_log = get_slurm_log(
        sinfo=sinfo,
        sdiag=sdiag,
        start_time=start_time,
        end_time=end_time,
        cluster=cluster,
        derived_cluster=cluster,
        logger=logger,
    )
    yield from slurm_log


@click_default_cmd(
    context_settings={
        "obj": _default_obj,
    },
)
@cluster_option
@sink_option
@sink_opts_option
@log_level_option
@log_folder_option
@stdout_option
@heterogeneous_cluster_v1_option
@interval_option(default=300)
@once_option
@retries_option
@dry_run_option
@chunk_size_option
@click.pass_obj
@typechecked
def main(
    obj: CliObject,
    cluster: Optional[str],
    sink: str,
    sink_opts: Collection[str],
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    log_folder: str,
    stdout: bool,
    heterogeneous_cluster_v1: bool,
    interval: int,
    once: bool,
    retries: int,
    dry_run: bool,
    chunk_size: int,
) -> None:
    """Publish SLURM metrics and logs from sacct, sdiag, and sinfo."""

    def collect_slurm_callable(
        cluster: str, interval: int, logger: logging.Logger
    ) -> Generator[SLURMLog | SLURMLogAccountMetrics, None, None]:
        return collect_slurm(
            obj=obj,
            interval=interval,
            cluster=cluster,
            logger=logger,
            heterogeneous_cluster_v1=heterogeneous_cluster_v1,
        )

    run_data_collection_loop(
        logger_name=LOGGER_NAME,
        log_folder=log_folder,
        stdout=stdout,
        log_level=log_level,
        cluster=obj.cluster() if cluster is None else cluster,
        clock=obj.clock,
        once=once,
        interval=interval,
        data_collection_tasks=[
            (
                collect_slurm_callable,
                SinkAdditionalParams(
                    data_type=DataType.METRIC,
                    heterogeneous_cluster_v1=heterogeneous_cluster_v1,
                ),
            ),
        ],
        sink=sink,
        sink_opts=sink_opts,
        retries=retries,
        chunk_size=chunk_size,
        dry_run=dry_run,
        registry=obj.registry,
    )
