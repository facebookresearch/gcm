# cluster-availability

## Overview
Monitors the percentage of cluster nodes in DOWN or DRAIN states against threshold values. Provides cluster-wide health status for availability monitoring.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--critical_threshold` | Integer (0-100) | 25 | Percentage of unavailable nodes for CRITICAL status |
| `--warning_threshold` | Integer (0-100) | 15 | Percentage of unavailable nodes for WARN status |
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
| **OK (0)** | Bad node percentage \<= warning_threshold |
| **WARN (1)** | Bad node percentage > warning_threshold OR command failed |
| **CRITICAL (2)** | Bad node percentage > critical_threshold |

## Usage Examples

### cluster-availability - Default Thresholds
```shell
health_checks check-service cluster-availability \
  [CLUSTER] \
  app
```

### cluster-availability - Custom Thresholds
```shell
health_checks check-service cluster-availability \
  --critical_threshold 30 \
  --warning_threshold 20 \
  [CLUSTER] \
  app
```

### cluster-availability - With Telemetry
```shell
health_checks check-service cluster-availability \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### cluster-availability - Debug Mode
```shell
health_checks check-service cluster-availability \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
