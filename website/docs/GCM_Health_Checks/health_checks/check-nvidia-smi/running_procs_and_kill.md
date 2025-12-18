# running_procs_and_kill

## Overview
Advanced process check with retry logic and optional force-kill capability for stuck processes. Implements multiple check attempts with configurable intervals before determining GPU availability status.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--running_procs_retry_count` | Integer | 3 | Number of retry attempts |
| `--running_procs_interval` | Integer | 3 | Seconds between retry attempts |
| `--running_procs_force_kill` | Flag | False | Force-kill processes if detected |
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
| **OK (0)** | No processes on first attempt |
| **WARN (1)** | Processes cleared after retries |
| **WARN (1)** | Processes killed successfully |
| **CRITICAL (2)** | Processes remain after retries |
| **CRITICAL (2)** | Force-kill failed |
| **UNKNOWN (3)** | NVML query failed |

## Usage Examples

### running_procs_and_kill - Basic with Retry
```shell
health_checks check-nvidia-smi \
  -c running_procs_and_kill \
  --running_procs_retry_count 3 \
  --running_procs_interval 3 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### running_procs_and_kill - Force Kill
```shell
health_checks check-nvidia-smi \
  -c running_procs_and_kill \
  --running_procs_retry_count 5 \
  --running_procs_interval 2 \
  --running_procs_force_kill \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
