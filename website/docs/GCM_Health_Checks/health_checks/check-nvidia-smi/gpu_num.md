# gpu_num

## Overview
Verifies the number of detected GPUs matches the expected count using `nvmlDeviceGetCount()`. Ensures the system has the correct GPU hardware configuration.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_num` | Integer | 8 | Expected number of GPUs |
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
| **OK (0)** | GPU count matches expected |
| **CRITICAL (2)** | GPU count mismatch |
| **UNKNOWN (3)** | NVML initialization failed |

## Usage Examples

### gpu_num - Basic Check
```shell
health_checks check-nvidia-smi \
  -c gpu_num \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### gpu_num - Custom GPU Count
```shell
health_checks check-nvidia-smi \
  -c gpu_num \
  --gpu_num 16 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
