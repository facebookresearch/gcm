# rocm_monitor

## Overview
Collects GPU metrics from **AMD GPUs** using the ROCm stack (`amd-smi` or `rocm-smi`) and publishes aggregated metrics at regular intervals. Provides real-time monitoring of GPU utilization, memory usage, power consumption, temperature, SLURM job information, and host-level metrics including RAM utilization. The schema matches `nvml_monitor` for consistency across NVIDIA and AMD deployments.

**Requirements**: `amd-smi` (preferred) or `rocm-smi` must be installed on the node and on PATH. See [AMD SMI](https://rocm.docs.amd.com/projects/amdsmi/).

**Data Type**: `DataType.LOG`, **Schemas**: `DevicePlusJobMetrics`

**Data Type**: `DataType.METRIC`, **Schemas**: `HostMetrics`, `IndexedDeviceMetrics`

## Execution Scope

All AMD GPU nodes in the cluster. Use `gcm nvml_monitor` on NVIDIA nodes and `gcm rocm_monitor` on AMD nodes (e.g. via systemd or scheduler).

## Environment Variables

- **ROCR_VISIBLE_DEVICES**: Optional. Comma-separated GPU indices visible to the process (ROCm analogue of `CUDA_VISIBLE_DEVICES`). If unset, all GPUs are visible.
- **SLURM_JOB_GPUS**: Used by job attribution when present in the process environment.

## Command-Line Options

Same as [nvml_monitor](nvml_monitor.md): `--collect-interval`, `--push-interval`, `--interval`, `--cluster`, `--sink`, `--sink-opts`, `--log-level`, `--log-folder`, `--stdout`, `--heterogeneous-cluster-v1`, `--once`, etc.

## Usage Examples

### Basic Continuous Monitoring
```bash
gcm rocm_monitor --sink file --sink-opts filepath=/tmp/amd_gpu_metrics.json
```

### One-Time Collection
```bash
gcm rocm_monitor --once --sink stdout
```

### systemd (AMD nodes)
Use the provided unit `systemd/rocm/rocm_monitor.service` and slice `systemd/rocm/fair_cluster_rocm_resources.slice` on AMD GPU nodes.
