# clock_freq

## Overview
Validates GPU and memory clock frequencies meet minimum application requirements using `nvmlDeviceGetClockInfo()`. Ensures GPUs operate at expected performance levels for workload execution.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_app_freq` | Integer | 1155 | Minimum GPU clock frequency (MHz) |
| `--gpu_app_mem_freq` | Integer | 1593 | Minimum memory clock frequency (MHz) |
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
| **OK (0)** | All GPUs meet frequency requirements |
| **CRITICAL (2)** | Any GPU below threshold |
| **UNKNOWN (3)** | NVML initialization failure |

## Usage Examples

### clock_freq - Basic Check
```shell
health_checks check-nvidia-smi \
  -c clock_freq \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### clock_freq - Custom Frequencies
```shell
health_checks check-nvidia-smi \
  -c clock_freq \
  --gpu_app_freq 1410 \
  --gpu_app_mem_freq 1800 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
