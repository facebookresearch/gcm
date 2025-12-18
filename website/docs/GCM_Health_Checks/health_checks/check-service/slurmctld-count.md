# slurmctld-count

## Overview
Verifies that the minimum number of Slurm controller daemons (slurmctld) are reachable from the node. Validates controller availability for cluster management operations.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--slurmctld-count` | Integer | **Required** | Minimum number of slurmctld daemons that should be present |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Condition | Message |
|-----------|-----------|---------|
| **OK (0)** | Feature flag disabled (killswitch active) | `Feature disabled by killswitch` |
| **OK (0)** | Reachable daemon count >= expected count | `Sufficient slurmctld daemon count. Expected at least: {n} and found: {n}` |
| **WARN (1)** | Command execution failed or invalid output | Error details with command output |
| **CRITICAL (2)** | Reachable daemon count < expected count | `Insufficient slurmctld daemon count. Expected at least: {n} and found: {n}` |

## Usage Examples

### slurmctld-count - Primary Only
```shell
health_checks check-service slurmctld-count \
  --slurmctld-count 1 \
  [CLUSTER] \
  app
```

### slurmctld-count - Primary + Backup
```shell
health_checks check-service slurmctld-count \
  --slurmctld-count 2 \
  [CLUSTER] \
  app
```

### slurmctld-count - With Telemetry
```shell
health_checks check-service slurmctld-count \
  --slurmctld-count 2 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### slurmctld-count - Debug Mode
```shell
health_checks check-service slurmctld-count \
  --slurmctld-count 2 \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
