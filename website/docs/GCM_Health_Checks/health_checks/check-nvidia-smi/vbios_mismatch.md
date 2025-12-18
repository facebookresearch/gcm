# vbios_mismatch

## Overview
Verifies consistent VBIOS versions across all GPUs using `nvmlDeviceGetVbiosVersion()`. If `--gpu_vbios` is not specified, auto-detects the expected version from the first GPU and validates all other GPUs match.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--gpu_vbios` | String | "" | Expected VBIOS version (auto-detect from first GPU if empty) |
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
| **OK (0)** | All GPUs have consistent VBIOS versions |
| **CRITICAL (2)** | VBIOS version mismatch detected |
| **UNKNOWN (3)** | Unable to retrieve VBIOS information |

## Usage Examples

### vbios_mismatch - Auto-Detect Check
```shell
health_checks check-nvidia-smi \
  -c vbios_mismatch \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### vbios_mismatch - Specify Expected Version
```shell
health_checks check-nvidia-smi \
  -c vbios_mismatch \
  --gpu_vbios "96.00.5E.00.01" \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
