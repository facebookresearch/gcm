# slurm_monitor

## Overview
Performs comprehensive analytics on SLURM cluster state by combining data from multiple sources (`sinfo`, `sdiag`, `sacct`) and computing aggregated metrics. Provides deep insights into cluster health, resource utilization, job analytics, and user activity.

**Data Type**: `DataType.METRIC`, **Schemas**: `SLURMLog`, `SLURMLogAccountMetrics`

## Execution Scope

Single node in the cluster.

## Metrics Collected

### SLURMLog
Published with `DataType.METRIC`:

```python
{
    # Cluster Identification
    "cluster": str,                          # Cluster name
    "derived_cluster": str,                  # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)

    # === USER ===
    "active_users": int | None,              # Users with running jobs
    "running_and_pending_users": int | None, # Users with running OR pending jobs

    # === JOB COUNTS ===
    "jobs_running": int | None,              # Currently running jobs
    "jobs_pending": int | None,              # Jobs waiting for resources
    "jobs_failed": int | None,               # Failed jobs in time window
    "jobs_without_user": int | None,         # Jobs missing user attribution
    "runaway_jobs": int | None,              # Long-running jobs (currently disabled), see https://slurm.schedmd.com/sacctmgr.html#OPT_RunawayJobs

    # === JOB ===
    # Jobs per user distribution
    "jobs_per_user_mean": float | None,      # Average jobs per active user
    "jobs_per_user_variance": float | None,  # Variance in jobs per user

    # Job runtime distribution (running jobs)
    "job_runtime_mean": float | None,        # Average job runtime (seconds)
    "job_runtime_variance": float | None,    # Variance in job runtime

    # Job wait time distribution (recently started jobs)
    "job_wait_time_mean": float | None,      # Average time from submit to start (seconds)
    "job_wait_time_variance": float | None,  # Variance in wait time

    # Job suspension distribution
    "job_suspended_mean": float | None,      # Average suspension time (seconds)
    "job_suspended_variance": float | None,  # Variance in suspension time

    # Distributed training metrics
    "jobs_dist_training_percent": float | None,  # % of jobs using multiple nodes

    # === RESOURCE ALLOCATIONS (Running Jobs) ===
    "avg_cpus_alloc_per_job": float | None,  # Average CPUs per running job
    "avg_gpus_alloc_per_job": float | None,  # Average GPUs per running job
    "total_cpus_alloc": int,                 # Total CPUs allocated to running jobs
    "total_gpus_alloc": int,                 # Total GPUs allocated to running jobs
    "total_nodes_alloc": int,                # Total nodes allocated to running jobs

    # === PENDING RESOURCES ===
    "gpus_pending": int | None,              # GPUs requested by pending jobs
    "nodes_pending": int | None,             # Nodes requested by pending jobs

    # === NODE STATE COUNTS === see https://slurm.schedmd.com/sinfo.html#SECTION_NODE-STATE-CODES
    "nodes_allocated": int | None,           # Fully allocated nodes
    "nodes_completing": int | None,          # Nodes completing jobs
    "nodes_down": int | None,                # Down nodes
    "nodes_drained": int | None,             # Drained nodes (no jobs accepted)
    "nodes_draining": int | None,            # Draining nodes (finishing jobs)
    "nodes_fail": int | None,                # Failed nodes
    "nodes_failing": int | None,             # Failing nodes
    "nodes_future": int | None,              # Future nodes
    "nodes_idle": int | None,                # Idle nodes (available)
    "nodes_inval": int | None,               # Invalid nodes
    "nodes_maint": int | None,               # Maintenance nodes
    "nodes_mixed": int | None,               # Partially allocated nodes
    "nodes_perfctrs": int | None,            # Performance counters enabled
    "nodes_planned": int | None,             # Planned nodes
    "nodes_power_down": int | None,          # Powering down
    "nodes_powered_down": int | None,        # Powered down
    "nodes_powering_down": int | None,       # In process of powering down
    "nodes_powering_up": int | None,         # In process of powering up
    "nodes_reboot_issued": int | None,       # Reboot issued
    "nodes_reboot_requested": int | None,    # Reboot requested
    "nodes_reserved": int | None,            # Reserved nodes
    "nodes_unknown": int | None,             # Unknown state
    "nodes_not_responding": int | None,      # Not responding
    "nodes_unknown_state": int | None,       # Unknown state
    "nodes_total": int | None,               # Total nodes
    "total_down_nodes": int | None,          # Down nodes according to `NODE_DOWN_STATES`, see https://github.com/facebookresearch/gcm/blob/main/gcm/monitoring/slurm/constants.py#L103

    # === RESOURCE TOTALS ===
    "total_cpus_avail": int | None,          # Total CPUs available in cluster
    "total_gpus_avail": int | None,          # Total GPUs available in cluster
    "total_cpus_up": int | None,             # CPUs on up nodes
    "total_gpus_up": int | None,             # GPUs on up nodes
    "total_cpus_down": int | None,           # CPUs on down nodes
    "total_gpus_down": int | None,           # GPUs on down nodes

    # === SCHEDULER METRICS (from Sdiag) === see https://slurm.schedmd.com/sdiag.html#SECTION_DESCRIPTION
    "server_thread_count": int | None,       # Server threads
    "agent_queue_size": int | None,          # Agent queue depth
    "agent_count": int | None,               # Number of agents
    "agent_thread_count": int | None,        # Agent threads
    "dbd_agent_queue_size": int | None,      # DBD agent queue depth
}
```

### SLURMLogAccountMetrics (Per-Account Metrics)
Published with `DataType.METRIC`, each slurm account has its own instance:

```python
{
    # Identification
    "account": str,                          # Slurm Account name
    "derived_cluster": str,                  # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)

    # Resource Allocations
    "total_cpus_alloc": int,                 # CPUs allocated to this account
    "total_gpus_alloc": int,                 # GPUs allocated to this account
    "total_nodes_alloc": int,                # Nodes allocated to this account

    # Job Analytics
    "job_runtime_mean": float | None,        # Average runtime for account's jobs
    "job_runtime_variance": float | None,    # Runtime variance for account's jobs
    "active_users": int | None,              # Active users in this account
    "jobs_dist_training_percent": float | None,  # % distributed training jobs
}
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cluster` | String | Auto-detected | Cluster name for metadata enrichment |
| `--sink` | String | **Required** | Sink destination, see [Exporters](../exporters/README.md) |
| `--sink-opts` | Multiple | - | Sink-specific options |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--stdout` | Flag | False | Display metrics to stdout in addition to logs |
| `--heterogeneous-cluster-v1` | Flag | False | Enable per-partition metrics for heterogeneous clusters |
| `--interval` | Integer | 300 | Seconds between collection cycles (5 minutes) |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink.  |

## Usage Examples

### Basic Continuous Monitoring
```shell
# Monitor nodes and jobs every minute (default)
gcm slurm_job_monitor --sink file --sink-opts file_path=/tmp/slurm_monitor.json
```

### One-Time Snapshot
```shell
# Get current cluster state once
gcm slurm_job_monitor --once --sink stdout
```

### Custom Batch Size for Large Clusters
```shell
gcm slurm_job_monitor \
  --chunk-size 2M \
  --interval 60 \
  --sink graph_api
```
