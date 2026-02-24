# mce

## Overview
Detects Machine Check Exception (MCE) errors by searching dmesg for `mce:` patterns. MCE errors indicate CPU or memory hardware issues that may affect system stability.

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
| **OK (0)** | No MCE errors detected |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | MCE errors detected |

## Usage Examples

### mce - Basic Check
```shell
health_checks check-syslogs mce [CLUSTER] app
```

### mce - Extended Timeout
```shell
health_checks check-syslogs mce \
  --timeout 60 \
   [CLUSTER] \
   app
```

### mce - Debug Mode
```shell
health_checks check-syslogs mce \
  --log-level DEBUG \
  --verbose-out \
   [CLUSTER] \
   app
```
