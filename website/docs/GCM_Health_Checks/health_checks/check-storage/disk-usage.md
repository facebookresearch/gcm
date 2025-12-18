# disk-usage

## Overview
Monitors disk space or inode usage on specified volumes with configurable warning and critical thresholds.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--volume` / `-v` | Path | **Required** | Volume(s) to check for free space (multiple allowed) |
| `--usage-critical-threshold` | Integer | 85 | Critical threshold percentage (0-100) |
| `--usage-warning-threshold` | Integer | 80 | Warning threshold percentage (0-100) |
| `--inode-check` / `--no-inode-check` | Flag | False | Check inode usage instead of disk space |
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
| **OK (0)** | Usage within limits |
| **WARN (1)** | Usage exceeds warning threshold |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Usage exceeds critical threshold |

## Usage Examples

### disk-usage - Single Volume
```shell
health_checks check-storage disk-usage \
  --volume /home \
  --usage-warning-threshold 75 \
  --usage-critical-threshold 90 \
  [CLUSTER] \
  app
```

### disk-usage - Multiple Volumes
```shell
health_checks check-storage disk-usage \
  --volume /home \
  --volume /scratch \
  --volume /tmp \
  [CLUSTER] \
  app
```

### disk-usage - Inode Check
```shell
health_checks check-storage disk-usage \
  --volume /var \
  --inode-check \
  --usage-critical-threshold 95 \
  [CLUSTER] \
  app
```

### disk-usage - With Telemetry
```shell
health_checks check-storage disk-usage \
  --volume /home \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
