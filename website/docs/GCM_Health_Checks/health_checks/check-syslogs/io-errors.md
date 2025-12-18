# io-errors

## Overview
Detects NVMe storage device errors by searching dmesg for I/O error messages. Extracts unique NVMe device names experiencing errors and triggers CRITICAL state if any I/O errors are detected.

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
| **OK (0)** | No I/O errors detected |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | NVMe I/O errors detected |

## Usage Examples

### io-errors - Basic Check
```shell
health_checks check-syslogs io-errors [CLUSTER] app
```

### io-errors - Debug Mode
```shell
health_checks check-syslogs io-errors \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
