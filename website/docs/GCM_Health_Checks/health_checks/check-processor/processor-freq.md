# processor-freq

## Overview
Validates that the CPU frequency meets or exceeds a specified minimum threshold by averaging frequency across all CPU cores.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--proc_freq` | Integer | 1498 | Minimum acceptable CPU frequency in MHz |
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
| **OK (0)** | CPU frequency ≥ threshold |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | CPU frequency < threshold |

## Usage Examples

### processor-freq - Basic Frequency Check
```shell
health_checks check-processor processor-freq \
  --sink stdout \
  [CLUSTER] \
  app
```

### processor-freq - Custom Frequency Threshold
```shell
health_checks check-processor processor-freq \
  --proc_freq 2000 \
  --sink stdout \
  [CLUSTER] \
  app
```

### processor-freq - With Telemetry
```shell
health_checks check-processor processor-freq \
  --proc_freq 1800 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### processor-freq - Debug Mode
```shell
health_checks check-processor processor-freq \
  --proc_freq 2400 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
