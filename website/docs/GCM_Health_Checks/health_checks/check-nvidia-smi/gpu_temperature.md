# gpu_temperature

## Overview
Ensures GPU temperatures remain below critical threshold using `nvmlDeviceGetTemperature()`. Prevents thermal throttling and hardware damage during workload execution.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_temperature_threshold` | Integer | **Required** | Maximum GPU temperature (°C) |
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

### gpu_temperature - Basic Check
```shell
health_checks check-nvidia-smi \
  -c gpu_temperature \
  --gpu_temperature_threshold 80 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### gpu_temperature - Custom Threshold
```shell
health_checks check-nvidia-smi \
  -c gpu_temperature \
  --gpu_temperature_threshold 85 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
