# nvml_monitor

## Overview
Collects GPU metrics from NVIDIA GPUs using the NVML (NVIDIA Management Library) API and publishes aggregated metrics at regular intervals. Provides real-time monitoring of GPU utilization, memory usage, power consumption, temperature, SLURM job information, and host-level metrics including RAM utilization.

**Data Type**: `DataType.LOG`, **Schemas**: `DevicePlusJobMetrics`

**Data Type**: `DataType.METRIC`, **Schemas**: `HostMetrics`, `IndexedDeviceMetrics`

## Execution Scope

All GPU nodes in the cluster.

## Metrics Collected

### DevicePlusJobMetrics
Published with `DataType.LOG`, 1 sample per host:

```python
{
    # Device Identification
    "gpu_id": int,                               # GPU index
    "hostname": str,                             # Node hostname

    # GPU Metrics
    "gpu_util": int,                             # GPU utilization (%)
    # Temperature & Power
    "temperature": int,                          # GPU temperature (°C)
    "power_draw": float,                         # Power usage (W)
    "power_used_percent": int,                   # Power usage (%)
    # Error Counts
    "retired_pages_count_single_bit": int,       # Single-bit ECC errors
    "retired_pages_count_double_bit": int,       # Double-bit ECC errors
    # GPU Memory
    "mem_util": int,                             # Memory utilization (%)
    "mem_used_percent": int,                     # Memory used (%)

    # SLURM Job Info (if job running on GPU)
    "job_id": str | None,                        # SLURM job ID
    "job_user": str | None,                      # Job owner
    "job_gpus": int | None,                      # GPUs allocated to job
    "job_num_gpus": int | None,                  # Number of GPUs used by job
    "job_num_cpus": int | None,                  # Number of CPUs used by job
    "job_name": str | None,                      # Job name
    "job_num_nodes": int | None,                 # Number of nodes allocated
    "job_partition": str | None,                 # Job partition
    "job_cpus_per_gpu": int | None,              # CPUs per GPU: job_num_cpus / job_num_gpus
}
```

### HostMetrics (Aggregated)
Published with `DataType.METRIC`:

```python
{
    # Host-Level GPU Aggregates
    "max_gpu_util": float,                       # Highest GPU utilization across all GPUs (%)
    "min_gpu_util": float,                       # Lowest GPU utilization across all GPUs (%)
    "avg_gpu_util": float,                       # Average GPU utilization (%)

    # Host RAM
    "ram_util": float,                           # Host RAM utilization (0.0-1.0)
}
```

### IndexedDeviceMetrics (Per GPU Aggregated)
Published with `DataType.METRIC`:

```python
{
    # GPU Metrics
    "gpu_util": int,                             # GPU utilization (%)
    # Temperature & Power
    "temperature": int,                          # GPU temperature (°C)
    "power_draw": float,                         # Power usage (W)
    "power_used_percent": int,                   # Power usage (%)
    # Error Counts
    "retired_pages_count_single_bit": int,       # Single-bit ECC errors
    "retired_pages_count_double_bit": int,       # Double-bit ECC errors
    # GPU Memory
    "mem_util": int,                             # Memory utilization (%)
    "mem_used_percent": int,                     # Memory used (%)
}
```

## Command-Line Options

### Output
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--collect-interval` | Integer | 10 seconds | Frequency to sample telemetry data |
| `--push-interval` | Integer | 60 seconds | Frequency to publish aggregated metrics |
| `--interval` | Integer | 90 seconds | Frequency to restart collection cycle |
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

## Usage Examples

### Basic Continuous Monitoring
```bash
gcm nvml_monitor --sink file --sink-opts filepath=/tmp/gpu_metrics.json
```

### One-Time Collection
```bash
gcm nvml_monitor --once --sink stdout
```

### Custom Intervals
```bash
# Sample every 5s, publish every 30s, restart every 60s
gcm nvml_monitor \
  --collect-interval 5 \
  --push-interval 30 \
  --interval 60 \
  --sink file --sink-opts filepath=/tmp/gpu_metrics.json
```

### Debug Mode with Console Output
```bash
gcm nvml_monitor \
  --log-level DEBUG \
  --stdout \
  --sink stdout
```
