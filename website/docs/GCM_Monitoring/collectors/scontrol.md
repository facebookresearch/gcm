# scontrol

## Overview
Collects SLURM partition configuration data using `scontrol show partition` and publishes individual partition records at regular intervals. Provides monitoring of partition-level configuration including resource limits (CPUs, memory, nodes, GPUs), TRES (Trackable RESources) allocations and billing weights, partition priority settings, QoS assignments, preempt modes, and node membership per partition.

Returns **multiple records** (one per partition), whereas `scontrol_config` returns a **single aggregated record** for cluster-wide configuration.

**Data Type**: `DataType.LOG`, **Schema**: `Scontrol`

## Execution Scope

Single node in the cluster.

## Output Schema

### Scontrol (Per Partition)
Published with `DataType.LOG`:

```python
{
    # Cluster Identification
    "cluster": str,                      # Cluster identifier
    "derived_cluster": str,              # Derived cluster for heterogeneous clusters

    # Partition Identity
    "Partition": str,                    # Partition name (from PartitionName)
    "Nodes": str,                        # Node list expression (e.g., "node[001-010]")

    # Resource Limits
    "MaxNodes": int,                     # Maximum nodes per job
    "TotalCPUs": int | None,             # Total CPUs in partition
    "TotalNodes": int | None,            # Total nodes in partition

    # TRES Allocations (extracted from TRES field)
    "TresCPU": int,                      # CPU allocation
    "TresMEM": int,                      # Memory allocation (bytes)
    "TresNODE": int,                     # Node allocation
    "TresBILLING": int,                  # Billing units
    "TresGRESGPU": int,                  # GPU allocation

    # TRES Billing Weights (from TRESBillingWeights)
    "TresBillingWeightCPU": int,         # CPU billing weight
    "TresBillingWeightMEM": int,         # Memory billing weight
    "TresBillingWeightGRESGPU": int,     # GPU billing weight

    # Priority Configuration
    "PriorityJobFactor": int | None,     # Job priority factor
    "PriorityTier": int | None,          # Partition priority tier
    "QoS": str,                          # Allowed QoS list
    "PreemptMode": str,                  # Preemption mode (OFF, CANCEL, etc.)
}
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--sink` | String | **Required** | Sink destination, see [Exporters](../exporters/README.md) |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--stdout` | Flag | False | Display metrics to stdout in addition to logs |
| `--interval` | Integer | 86400 | Frequency in seconds to collect data (24 hours) |
| `--once` | Flag | False | Run once and exit |
| `--cluster` | String | Auto-detected | Cluster identifier |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--retries` | Integer | 3 | Number of retries on failure |
| `--dry-run` | Flag | False | Run without sending data to sink |
| `--chunk-size` | Integer | 1000 | The maximum size in bytes of each chunk when writing data to sink |

## Usage Examples

### Basic Daily Collection
```bash
gcm scontrol --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}"
```

### One-Time Snapshot
```bash
gcm scontrol --once --sink stdout
```

### Hourly Collection
```bash
# Monitor partition changes more frequently
gcm scontrol --interval 3600 --sink file --sink-opts filepath=/tmp/partitions.json
```
