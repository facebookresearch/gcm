# sacctmgr_user

## Overview
Collects user account and association data from SLURM using `sacctmgr` and publishes it at regular intervals. Provides daily snapshots of user account associations, default accounts and QoS per user, account-specific QoS access, user permissions and access control, and account hierarchy.

**Data Type**: `DataType.LOG`, **Schema**: `SacctmgrUserPayload`

## Execution Scope

Single node in the cluster.

## Output Schema

### SacctmgrUserPayload
Published with `DataType.LOG`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "sacctmgr_user": {            # Dictionary of user attributes
        "User": str,              # Username
        "DefaultAccount": str,    # User's default account
        "Account": str,           # Account for this association
        "DefaultQOS": str,        # User's default QoS
        "QOS": str,               # Comma-separated list of available QoS
        # Additional fields depending on SLURM version
    }
}
```

**Important Notes:**
1. Each user-account association creates a separate record
2. A user with 3 accounts will generate 3 separate payloads
3. The `QOS` field is a comma-separated string of available QoS levels
4. Fields depend on SLURM version; collector dynamically parses headers

### Data Collection Commands
The collector executes:

**Stage 1: Get User List**
```bash
sacctmgr show user format=User -nP
```

**Stage 2: Get User Details (per user)**
```bash
sacctmgr show user <username> withassoc format=User,DefaultAccount,Account,DefaultQOS,QOS -P
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

### Basic Daily Collection
```bash
gcm sacctmgr_user --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm sacctmgr_user --once --sink stdout
```

### Debug Mode with Local File Output
```bash
gcm sacctmgr_user \
  --once \
  --log-level DEBUG \
  --stdout \
  --sink file --sink-opts filepath=/tmp/user_data.jsonl
```
