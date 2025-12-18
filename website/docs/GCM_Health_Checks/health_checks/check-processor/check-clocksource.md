# check-clocksource

## Overview
Validates that the system uses the expected clock source for timekeeping. The clock source affects time synchronization accuracy which is critical for distributed systems and scheduling.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--expected-source` | String | **Required** | Expected clocksource (e.g., `tsc`, `hpet`) |
| `--sys-clocksource-file` | String | `/sys/devices/system/clocksource/clocksource0/current_clocksource` | Path to clocksource file |
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
| **OK (0)** | Clocksource matches expected |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Clocksource mismatch |

## Usage Examples

### check-clocksource - TSC Clocksource Check
```shell
health_checks check-processor check-clocksource \
  --expected-source tsc \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-clocksource - HPET Clocksource Check
```shell
health_checks check-processor check-clocksource \
  --expected-source hpet \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-clocksource - Custom Clocksource Path
```shell
health_checks check-processor check-clocksource \
  --expected-source tsc \
  --sys-clocksource-file /sys/custom/clocksource \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-clocksource - Debug Mode
```shell
health_checks check-processor check-clocksource \
  --expected-source tsc \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
