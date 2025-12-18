# gpu_mem_usage

## Overview
Verifies GPU memory usage is below threshold using `nvmlDeviceGetMemoryInfo()`. Ensures proper cleanup validation and prevents memory leaks between job executions.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_mem_usage_threshold` | Integer | 15 | Maximum GPU memory usage (MiB) |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All GPUs below threshold |
| **CRITICAL (2)** | Any GPU exceeds threshold |
| **UNKNOWN (3)** | NVML initialization failure |

## Usage Examples

### gpu_mem_usage - Basic Check
```shell
health_checks check-nvidia-smi \
  -c gpu_mem_usage \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### gpu_mem_usage - Epilog Cleanup Validation
```shell
health_checks check-nvidia-smi \
  -c gpu_mem_usage \
  --gpu_mem_usage_threshold 10 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  epilog
```
