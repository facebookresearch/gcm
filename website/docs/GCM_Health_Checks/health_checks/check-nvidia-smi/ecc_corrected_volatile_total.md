# ecc_corrected_volatile_total

## Overview
Monitors corrected ECC error accumulation to detect degrading memory health. High corrected error counts may indicate impending hardware failure.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ecc_corrected_volatile_threshold` | Integer | 50000000 | Maximum allowed corrected ECC errors |
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
| **OK (0)** | Corrected errors below threshold |
| **CRITICAL (2)** | Corrected errors exceed threshold |
| **UNKNOWN (3)** | Unable to query ECC status |

## Usage Examples

### Basic Check
```shell
health_checks check-nvidia-smi \
  -c ecc_corrected_volatile_total \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Custom Threshold
```shell
health_checks check-nvidia-smi \
  -c ecc_corrected_volatile_total \
  --ecc_corrected_volatile_threshold 10000000 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
