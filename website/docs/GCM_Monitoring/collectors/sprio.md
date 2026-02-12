# sprio

## Overview
Collects SLURM job priority information using `sprio` and publishes it at regular intervals. This enables FAIR Passport and other tools to display job priority factors for users across clusters.

**Data Type**: `DataType.LOG`, **Schema**: `SprioPayload`

## Execution Scope

Single node in the cluster.

## Output Schema

### SprioPayload
Published with `DataType.LOG`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "collection_unixtime": int,   # Unix timestamp of collection (for snapshot identification)
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (same as cluster if not `--heterogeneous-cluster-v1`)
    "sprio": {                    # Dictionary of job priority attributes
        "JOBID": float,           # Job ID
        "PARTITION": str,         # Partition name
        "USER": str,              # Username
        "ACCOUNT": str,           # Account name
        "PRIORITY": float,        # Total priority score
        "SITE": float,            # Site priority factor
        "AGE": float,             # Age priority factor
        "ASSOC": str,             # Association priority factor
        "FAIRSHARE": float,       # Fairshare priority factor
        "JOBSIZE": float,         # Job size priority factor
        "PARTITION_PRIO": float,  # Partition priority factor
        "QOSNAME": str,           # QoS name
        "QOS": str,               # QoS priority factor
        "NICE": float,            # Nice value adjustment
    }
}
```

**Important Notes:**
1. Each pending job creates a separate record
2. Numeric priority factors are floats; identifiers are strings

### Data Collection Commands
The collector executes:

```bash
sprio -h --sort=r,-y -o "%i|%r|%u|%o|%Y|%S|%a|%A|%F|%J|%P|%n|%Q|%N"
```

The custom format string avoids duplicate column names that appear in `sprio -l` output. Jobs are sorted by partition (ascending) and priority (descending).

> **Implementation Note**: This format string is auto-generated from the [`SprioRow`](../../../../gcm/schemas/slurm/sprio.py) dataclass. Each field's `format_code` metadata defines the corresponding sprio format specifier. To add or modify fields, update `SprioRow` - the format string regenerates automatically.

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
| `--interval` | Integer | 120 | Seconds between collection cycles (2 minutes) |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink. |

## Usage Examples

### Basic Continuous Collection
```bash
gcm sprio --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm sprio --once --sink stdout
```

### Debug Mode with Local File Output
```bash
gcm sprio \
  --once \
  --log-level DEBUG \
  --stdout \
  --sink file --sink-opts filepath=/tmp/sprio_data.jsonl
```
