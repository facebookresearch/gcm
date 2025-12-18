# running_procs

## Overview
Checks for processes occupying GPUs using `nvmlDeviceGetComputeRunningProcesses()`. Ensures GPUs are idle and available for new workloads.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
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
| **OK (0)** | No active processes found |
| **OK (0)** | Only zombie PIDs detected |
| **CRITICAL (2)** | Real processes found |
| **UNKNOWN (3)** | NVML query failed |

## Usage Examples

### running_procs - Basic Check
```shell
health_checks check-nvidia-smi \
  -c running_procs \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
