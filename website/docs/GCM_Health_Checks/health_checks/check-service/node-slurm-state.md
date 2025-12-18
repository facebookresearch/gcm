# node-slurm-state

## Overview
Checks if the node is in a Slurm state that allows it to accept jobs. Validates individual node health and availability for workload execution.

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
| **OK (0)** | Node in good state and can accept jobs |
| **WARN (1)** | Node in critical state, undefined state, or command failed |

## Usage Examples

### node-slurm-state - Basic Check
```shell
health_checks check-service node-slurm-state \
  [CLUSTER] \
  app
```

### node-slurm-state - With Telemetry
```shell
health_checks check-service node-slurm-state \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### node-slurm-state - Debug Mode
```shell
health_checks check-service node-slurm-state \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```

### node-slurm-state - With Timeout
```shell
health_checks check-service node-slurm-state \
  --timeout 30 \
  [CLUSTER] \
  app
```
