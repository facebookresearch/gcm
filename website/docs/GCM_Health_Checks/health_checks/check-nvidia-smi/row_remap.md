# row_remap

## Overview
Checks for pending or failed memory row remapping operations using `nvmlDeviceGetRowRemapperHistogram()`. Row remapping indicates memory defects requiring GPU reset or replacement.

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
| **OK (0)** | No pending or failed remaps |
| **CRITICAL (2)** | Pending remaps detected |
| **CRITICAL (2)** | Failed remaps detected |
| **UNKNOWN (3)** | Unable to query remap status |

## Usage Examples

### Basic Check
```shell
health_checks check-nvidia-smi \
  -c row_remap \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
