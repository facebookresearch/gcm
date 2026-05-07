# slurm_job_monitor

## Overview
Collects dual-stream real-time data from SLURM: node metrics via `sinfo` and job metrics via `squeue`. Provides lightweight, high-frequency snapshots of cluster infrastructure state and active workload for real-time monitoring, capacity planning, resource utilization tracking, and bottleneck detection.

**Data Type**: `DataType.LOG`

**Data Identifiers**: `DataIdentifier.NODE` (node data), `DataIdentifier.JOB` (job data)

**Schemas**: `NodeData` (nodes), `JobData` (jobs)

The collector publishes **two separate data streams** with distinct `DataIdentifier` values for independent indexing, scaling, and targeted analysis.

## Execution Scope

Single node in the cluster.

## Output Schema

### NodeData (Node Infrastructure)
Published with `DataType.LOG` and `DataIdentifier.NODE`:

```python
{
    # Metadata
    "num_rows": int,                    # Total nodes in this collection
    "collection_unixtime": int,         # Collection timestamp (Unix epoch)
    "cluster": str,                     # Cluster name
    "derived_cluster": str,             # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)

    # Node Identification
    "NODE_NAME": str,                   # Node hostname
    "PARTITION": str,                   # Partition assignment

    # CPU Resources
    "CPUS_ALLOCATED": int,              # CPUs currently allocated to jobs
    "CPUS_IDLE": int,                   # CPUs available (idle)
    "CPUS_OTHER": int,                  # CPUs in other state
    "CPUS_TOTAL": int,                  # Total CPUs on node

    # Memory Resources
    "FREE_MEM": int | None,             # Free memory (MB)
    "MEMORY": int | None,               # Total memory (MB)

    # GPU Resources
    "NUM_GPUS": int,                    # Number of GPUs on node

    # Node State
    "STATE": str,                       # Node state (idle, allocated, down, etc.)
    "REASON": str,                      # Reason for down/drain state
    "USER": str,                        # User if node reserved
    "RESERVATION": str,                 # Reservation name if applicable

    # Node Metadata
    "TIMESTAMP": str,                   # Last sinfo update
    "ACTIVE_FEATURES": str,             # Active node features/constraints
}
```

### JobData (Job Queue)
Published with `DataType.LOG`:

```python
{
    # Metadata
    "collection_unixtime": int,         # Collection timestamp (Unix epoch)
    "cluster": str,                     # Cluster name
    "derived_cluster": str,             # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)

    # Job Identification
    "JOBID": str,                       # Job array ID
    "JOBID_RAW": str,                   # Raw job ID (includes array indices)
    "NAME": str,                        # Job name
    "USER": str,                        # Username
    "ACCOUNT": str,                     # Account/project
    "PARTITION": str,                   # Partition name
    "QOS": str,                         # Quality of Service

    # Job State
    "STATE": str,                       # Job state (RUNNING, PENDING, etc.)
    "REASON": str,                      # Reason for pending state
    "PRIORITY": float | None,           # Job priority
    "PENDING_RESOURCES": str,           # Resources preventing job from running

    # Resource Requests
    "CPUS": int | None,                 # CPUs requested
    "MIN_CPUS": int | None,             # Minimum CPUs per node
    "NODES": int | None,                # Nodes requested
    "GPUS_REQUESTED": int | None,       # GPUs requested (from TRES-PER-NODE)
    "MIN_MEMORY": int,                  # Memory requested (MB)

    # TRES Allocations (for running jobs)
    "TRES_CPU_ALLOCATED": int,          # CPUs allocated
    "TRES_GPUS_ALLOCATED": int,         # GPUs allocated
    "TRES_MEM_ALLOCATED": int,          # Memory allocated (MB)
    "TRES_NODE_ALLOCATED": int,         # Nodes allocated
    "TRES_BILLING_ALLOCATED": int,      # Billing units allocated

    # Time Information
    "SUBMIT_TIME": str,                 # Job submission time (ISO 8601)
    "ELIGIBLE_TIME": str,               # Time job became eligible to run
    "START_TIME": str,                  # Job start time (or estimated for pending)
    "ACCRUE_TIME": str,                 # Time job started accruing priority
    "TIME_USED": str,                   # Elapsed time (HH:MM:SS)
    "TIME_LEFT": str,                   # Remaining time (HH:MM:SS)
    "TIME_LIMIT": str,                  # Time limit (HH:MM:SS)
    "PENDING_TIME": int | None,         # Seconds job has been pending

    # Node Assignment
    "NODELIST": list[str] | None,       # Assigned nodes (for running jobs)
    "SCHEDNODES": list[str] | None,     # Nodes under consideration for scheduling
    "EXC_NODES": list[str] | None,      # Excluded nodes

    # Scheduling & Dependencies
    "DEPENDENCY": str,                  # Job dependencies
    "RESERVATION": str,                 # Reservation if applicable
    "FEATURE": str,                     # Required node features
    "REQUEUE": str,                     # Whether job can be requeued
    "RESTARTCNT": int,                  # Number of restarts
    "COMMENT": str,                     # Job comment
    "COMMAND": str,                     # Job command/script
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
| `--interval` | Integer | 60 | Seconds between collection cycles |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink |

## Usage Examples

### Basic Continuous Monitoring
```bash
# Monitor nodes and jobs every minute (default)
gcm slurm_job_monitor --sink graph_api --sink-opts scribe_category=slurm_realtime
```

### High-Frequency Monitoring
```bash
# Check every 30 seconds
gcm slurm_job_monitor --interval 30 --sink graph_api
```

### One-Time Snapshot
```bash
# Get current cluster state once
gcm slurm_job_monitor --once --sink stdout
```

### Dry Run for Testing
```bash
# Test without publishing to production sink
gcm slurm_job_monitor --once --dry-run
```

### File Output
```bash
# Save to local files
gcm slurm_job_monitor \
  --once \
  --sink file \
  --sink-opts filepath=/tmp/slurm_data.json
```
