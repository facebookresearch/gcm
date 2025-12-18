# check-buddyinfo

## Overview
Queries `/proc/buddyinfo` to detect memory fragmentation by verifying sufficient free memory blocks of higher orders exist.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--buddyinfo_path` | Path | `/proc/buddyinfo` | Path to buddyinfo file |
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
| **OK (0)** | Sufficient large memory blocks |
| **WARN (1)** | Failed to read buddyinfo |
| **CRITICAL (2)** | Memory fragmentation detected |

## Usage Examples

### check-buddyinfo - Standard Fragmentation Check
```shell
health_checks check-processor check-buddyinfo \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-buddyinfo - Custom Buddyinfo Path
```shell
health_checks check-processor check-buddyinfo \
  --buddyinfo_path /custom/proc/buddyinfo \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-buddyinfo - With Telemetry
```shell
health_checks check-processor check-buddyinfo \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-buddyinfo - Debug Mode
```shell
health_checks check-processor check-buddyinfo \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
