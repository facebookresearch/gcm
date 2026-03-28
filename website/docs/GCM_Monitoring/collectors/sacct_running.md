# sacct_running

## Overview
Continuously monitors SLURM jobs in running state (`RUNNING` or `R`) through the `sacct` command and publishes records at regular intervals. Provides real-time visibility into active job execution, resource utilization tracking, detection of long-running or stuck jobs, and current snapshot of cluster activity. Unlike `sacct_backfill` which processes historical data, `sacct_running` focuses exclusively on jobs currently executing on the cluster.

**Data Type**: `DataType.LOG`, **Schema**: `Sacct`

## Execution Scope

Single node in the cluster.

## Output Schema

### Sacct
Published with `DataType.LOG`:

```python
{
    # SLURM Fields (from sacct -o all)
    "JobID": str,                            # Job identifier
    "JobIDRaw": str,                         # Raw job ID
    "JobName": str,                          # User-specified job name
    "User": str,                             # Job owner
    "Account": str,                          # SLURM account
    "Partition": str,                        # Job partition
    "State": str,                            # Job state (RUNNING, R)
    "ExitCode": str,                         # Exit code
    "AllocCPUs": int,                        # Allocated CPUs
    "ReqMem": str,                           # Requested memory
    "AllocNodes": int,                       # Allocated nodes
    # ... plus 40+ additional sacct fields

    # Timestamps
    "Start": str,                            # Job start time
    "Submit": str,                           # Submission time
    "Eligible": str,                         # Eligible time
    "End": str,                              # Typically "Unknown" for running jobs

    # Enriched Fields
    "cluster": str,                          # Cluster name
    "derived_cluster": str,                  # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "time": int,                             # Collection timestamp (Unix epoch)
    "end_ds": str,                           # Date string in Pacific Time (YYYY-MM-DD)
}
```

**Note:** The exact fields depend on the SLURM version. See [sacct documentation](https://slurm.schedmd.com/sacct.html) for details.

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
| `--delimiter` | String | `\|#` | Field delimiter, must be unique enough such that no field has an instance of the delimiter. User input fields like `job name` can break parsing. |

## Usage Examples

### Basic Continuous Monitoring
```bash
# Monitor running jobs every hour (default)
gcm sacct_running --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### High-Frequency Monitoring
```bash
# Check running jobs every 5 minutes
gcm sacct_running --interval 300 --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
# Get current running jobs once
gcm sacct_running --once --sink stdout
```

### File Output
```bash
# Save to local file
gcm sacct_running \
  --once \
  --sink file \
  --sink-opts filepath=/tmp/running_jobs.json
```
