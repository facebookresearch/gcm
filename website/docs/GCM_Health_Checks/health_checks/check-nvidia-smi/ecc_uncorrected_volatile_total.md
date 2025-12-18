# ecc_uncorrected_volatile_total

## Overview
Validates that uncorrected ECC error counts remain within acceptable range. Uncorrected errors indicate unrecoverable memory corruption requiring immediate attention.

## Requirements
- NVIDIA GPU Drivers

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ecc_uncorrected_volatile_threshold` | Integer | 0 | Maximum allowed uncorrected ECC errors |
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
| **OK (0)** | Uncorrected errors below threshold |
| **CRITICAL (2)** | Uncorrected errors exceed threshold |
| **UNKNOWN (3)** | Unable to query ECC status |

## Usage Examples

### Basic Check
```shell
health_checks check-nvidia-smi \
  -c ecc_uncorrected_volatile_total \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Custom Threshold
```shell
health_checks check-nvidia-smi  \
  -c ecc_uncorrected_volatile_total \
  --ecc_uncorrected_volatile_threshold 5 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
