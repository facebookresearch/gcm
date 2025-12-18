# check-running-process

## Overview
Validates that one or more specified processes are currently running on the system. Uses `ps` command to detect active processes with automatic filtering of grep and self-detection.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--process-name` / `-p` | String | **Required** | Process name to verify (repeatable) |
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
| **OK (0)** | All processes are running |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Process not running |

**Multi-Process**: Overall exit code is maximum (worst) of all individual checks.

## Usage Examples

### check-running-process - Single Process
```shell
health_checks check-process check-running-process \
  --process-name nvidia-smi \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-running-process - Multiple Processes
```shell
health_checks check-process check-running-process \
  --process-name dcgmi \
  --process-name nvidia-smi \
  --process-name slurmd \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-running-process - Custom Timeout
```shell
health_checks check-process check-running-process \
  --process-name monitoring-agent \
  --timeout 60 \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-running-process - Debug Mode
```shell
health_checks check-process check-running-process \
  --process-name myapp \
  --log-level DEBUG \
  --verbose-out \
  --sink file --sink-opts filepath=/var/log/process_check.json \
  [CLUSTER] \
  app
```
