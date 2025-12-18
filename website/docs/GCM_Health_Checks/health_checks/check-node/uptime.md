# uptime

## Overview
Verifies that the compute node has been running long enough to be considered stable. Warns if the node recently rebooted, which may indicate maintenance or instability.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--uptime-threshold` | Integer | 600 seconds | Minimum uptime before WARN condition (default: 10 minutes) |
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
| **OK (0)** | Uptime exceeds threshold |
| **WARN (1)** | Uptime below threshold |
| **WARN (1)** | Command execution failed |

## Usage Examples

### Basic Uptime Check
```shell
# 5 minute threshold (300 seconds)
health_checks check-node uptime \
  --uptime-threshold 300 \
  [CLUSTER] \
  app
```

### With Telemetry
```shell
health_checks check-node uptime \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  --verbose-out \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-node uptime \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
