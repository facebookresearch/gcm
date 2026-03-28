# sacctmgr_qos

## Overview
Collects Quality of Service (QoS) configuration data from SLURM using `sacctmgr` and publishes it at regular intervals. Provides daily snapshots of QoS resource limits (CPU, memory, GPU, wall time), priorities and preemption settings, usage limits per user/group, grace periods and runtime constraints, and QoS hierarchies. Enables tracking of QoS configuration changes over time.

**Data Type**: `DataType.LOG`, **Schema**: `SacctmgrQosPayload`

## Execution Scope

Single node in the cluster (typically head node).

## Output Schema

### SacctmgrQosPayload
Published with `DataType.LOG`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "sacctmgr_qos": {             # Dictionary of QoS attributes
        "Name": str,              # QoS name
        "Priority": str,          # Job priority
        "GraceTime": str,         # Grace period before preemption
        "Preempt": str,           # QoS that can be preempted
        "PreemptExemptTime": str, # Time before job can be preempted
        "PreemptMode": str,       # Preemption mode (cancel, requeue, suspend)
        "Flags": str,             # QoS flags
        "UsageThres": str,        # Usage threshold
        "UsageFactor": str,       # Usage factor for fair-share
        "GrpTRES": str,           # Group TRES limits
        "GrpTRESMins": str,       # Group TRES-minutes limits
        "GrpTRESRunMins": str,    # Group running TRES-minutes limits
        "GrpJobs": str,           # Max concurrent jobs per group
        "GrpSubmit": str,         # Max submitted jobs per group
        "GrpWall": str,           # Max wall time per group
        "MaxTRES": str,           # Max TRES per job
        "MaxTRESMins": str,       # Max TRES-minutes per job
        "MaxTRESPerNode": str,    # Max TRES per node
        "MaxJobs": str,           # Max concurrent jobs per user
        "MaxSubmit": str,         # Max submitted jobs per user
        "MaxWall": str,           # Max wall time per job
        "MinTRES": str,           # Min TRES per job
        # Additional fields depending on SLURM version
    }
}
```

**Note:** The exact fields in `sacctmgr_qos` dictionary depend on the SLURM version. The collector dynamically parses the header line to determine available fields.

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

### Basic Daily Collection
```bash
gcm sacctmgr_qos --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm sacctmgr_qos --once --sink stdout
```

### Custom Collection Interval
```bash
# Collect every 6 hours
gcm sacctmgr_qos --interval 21600 --sink graph_api
```

### File Output
```bash
gcm sacctmgr_qos \
  --once \
  --sink file \
  --sink-opts filepath=/tmp/qos_data.jsonl
```
