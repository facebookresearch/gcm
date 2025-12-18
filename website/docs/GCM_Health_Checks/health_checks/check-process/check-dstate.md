# check-dstate

## Overview
Detects processes stuck in uninterruptible sleep (D-state) that exceed a specified age threshold. Identifies processes blocked on I/O operations or kernel calls that may indicate system issues.

> D-state processes are typically waiting on disk I/O, network operations, or other kernel resources. Prolonged D-state indicates potential hardware or driver issues.

## Dependencies

- **strace**: System call tracer for process inspection

### Package Installation
```shell
# RHEL/CentOS
yum install procps-ng strace

# Ubuntu/Debian
apt-get install procps strace
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--elapsed` | Integer | 300 | Minimum process age (seconds) to trigger failure |
| `--process-name` | String | - | Filter by process name (regex supported); can specify multiple |
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
| **OK (0)** | No D-state processes exceed age threshold |
| **WARN (1)** | Exception during process check execution |
| **CRITICAL (2)** | One or more processes stuck in D-state |

## Usage Examples

### Basic Check (Default 5 Minutes)
```shell
health_checks check-process check-dstate [CLUSTER] app
```

### Custom Age Threshold (10 Minutes)
```shell
health_checks check-process check-dstate \
  --elapsed 600
  [CLUSTER] \
  app
```

### Filter Specific Process
```shell
health_checks check-process check-dstate \
  --process-name "nfs.*" \
  --elapsed 180 \
  [CLUSTER] \
  app
```

### Multiple Process Filters
```shell
health_checks check-process check-dstate \
  --process-name "nfs.*" \
  --process-name "mount.*" \
  --process-name "umount.*" \
  --elapsed 300 \
  [CLUSTER] \
  app
```

### With Telemetry
```shell
health_checks check-process check-dstate \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  --verbose-out \
  [CLUSTER] \
  prolog
```

### Debug Mode
```shell
health_checks -dstate \
  --log-level DEBUG \
  --verbose-out
  [CLUSTER] \
  app
```
