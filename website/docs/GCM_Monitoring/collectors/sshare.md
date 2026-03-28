# sshare

## Overview
Collects SLURM fair-share scheduling data using `sshare` and publishes it at regular intervals. This provides visibility into account-level fair-share factors, resource usage, and scheduling priorities across the cluster.

**Data Type**: `DataType.LOG`, **Schema**: `SsharePayload`

## Execution Scope

Single node in the cluster.

## Output Schema

### SsharePayload
Published with `DataType.LOG`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "collection_unixtime": int,   # Unix timestamp of collection (for snapshot identification)
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "sshare": {                   # Dictionary of fair-share attributes
        "Account": str,           # Account name
        "User": str,              # Username (empty for account-level rows)
        "RawShares": str,         # Raw shares allocation
        "NormShares": str,        # Normalized shares (0.0-1.0)
        "RawUsage": str,          # Raw usage value
        "NormUsage": str,         # Normalized usage (0.0-1.0)
        "EffectvUsage": str,      # Effective usage after tree decay
        "FairShare": str,         # Fair-share factor (0.0-1.0)
        "GrpTRESMins": str,       # Group TRES-minutes limit
        "TRESRunMins": str,       # TRES-minutes consumed by running jobs
    }
}
```

**Important Notes:**
1. Each account/user combination creates a separate record
2. Account-level rows have an empty `User` field
3. All sshare fields are strings as returned by the `sshare` command

### Data Collection Commands
The collector executes:

```bash
sshare -a -P
```

The `-a` flag includes all accounts and the `-P` flag produces parseable pipe-delimited output. See [sshare documentation](https://slurm.schedmd.com/sshare.html).

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
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink. |

## Usage Examples

### Basic Continuous Collection
```bash
gcm sshare --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm sshare --once --sink stdout
```

### Debug Mode with Local File Output
```bash
gcm sshare \
  --once \
  --log-level DEBUG \
  --stdout \
  --sink file --sink-opts filepath=/tmp/sshare_data.jsonl
```
