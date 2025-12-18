# check-sensors

## Overview
Monitors hardware health by detecting fan and power supply errors through IPMI (Intelligent Platform Management Interface) sensors.

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

| Exit Code | Description |
|-----------|-------------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | No sensor errors detected |
| **WARN (1)** | PSU redundancy issue detected OR ipmi-sensors command failed |
| **CRITICAL (2)** | Fan error detected OR PSU error detected |
| **UNKNOWN (3)** | Command execution error before parsing |

## Usage Examples

### Basic Sensor Check
```shell
health_checks check-sensors [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-sensors \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
