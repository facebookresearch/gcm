# disk-size

## Overview
Validates disk size meets specified criteria using comparison operators.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--volume` / `-v` | Path | **Required** | Volume to check size |
| `--size-unit` | Choice | K | Size unit: K, M, G, T (kilobytes, megabytes, gigabytes, terabytes) |
| `--operator` | Choice | **Required** | Comparison operator: `>`, `<`, `=`, `<=`, `>=` |
| `--value` | Integer | **Required** | Value to compare against |
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
| **OK (0)** | Size meets criteria |
| **WARN (1)** | Command execution fails |
| **CRITICAL (2)** | Size comparison fails |

## Usage Examples

### disk-size - Minimum Size Check
```shell
health_checks check-storage disk-size \
  --volume /scratch \
  --size-unit T \
  --operator ">=" \
  --value 10 \
  [CLUSTER] \
  app
```

### disk-size - Maximum Size Check
```shell
health_checks check-storage disk-size \
  --volume /tmp \
  --size-unit G \
  --operator "<=" \
  --value 500 \
  [CLUSTER] \
  app
```

### disk-size - Exact Size Check
```shell
health_checks check-storage disk-size \
  --volume /boot \
  --size-unit M \
  --operator "=" \
  --value 512 \
  [CLUSTER] \
  app
```

### disk-size - With Timeout
```shell
health_checks check-storage disk-size \
  --volume /scratch \
  --size-unit T \
  --operator ">=" \
  --value 10 \
  --timeout 30 \
  [CLUSTER] \
  app
```
