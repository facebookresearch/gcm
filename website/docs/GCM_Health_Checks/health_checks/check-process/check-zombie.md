# check_zombie

## Overview
Detects zombie processes (defunct processes in state 'Z') that have persisted beyond a configurable threshold. Zombie processes indicate parent processes failing to reap child processes and may signal application bugs or system issues.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--elapsed` | Integer | 300 | Age threshold in seconds for zombie processes |
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
| **OK (0)** | No zombie processes exceed threshold |
| **WARN (1)** | Zombie processes exceed age threshold |
| **UNKNOWN (3)** | Command execution failed |

## Usage Examples

### check-zombie - Basic Detection
```shell
health_checks check-process check-zombie \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-zombie - Custom Threshold
```shell
health_checks check-process check-zombie \
  --elapsed 600 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-zombie - With Telemetry
```shell
health_checks check-process check-zombie \
  --elapsed 300 \
  --timeout 60 \
  --sink file --sink-opts filepath=/var/log/zombie_check.json \
  [CLUSTER] \
  app
```

### check-zombie - Debug Mode
```shell
health_checks check-process check-zombie \
  --elapsed 120 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
