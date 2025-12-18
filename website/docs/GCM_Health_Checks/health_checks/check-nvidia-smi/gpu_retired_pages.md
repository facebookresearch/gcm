# gpu_retired_pages

## Overview
Checks retired memory pages due to ECC errors don't exceed limits. Identifies GPUs with excessive memory errors that may indicate hardware degradation requiring maintenance.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_retired_pages_threshold` | Integer | 10 | Maximum retired pages count |
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
| **OK (0)** | All counts below threshold and no pending |
| **CRITICAL (2)** | Threshold exceeded or pending > 0 |
| **UNKNOWN (3)** | NVML initialization failure |

## Usage Examples

### gpu_retired_pages - Basic Check
```shell
health_checks check-nvidia-smi \
  -c gpu_retired_pages \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### gpu_retired_pages - Custom Threshold
```shell
health_checks check-nvidia-smi \
  -c gpu_retired_pages \
  --gpu_retired_pages_threshold 5 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
