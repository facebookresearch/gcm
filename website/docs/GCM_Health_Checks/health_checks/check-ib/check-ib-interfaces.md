# check-ib-interfaces

## Overview
Validates that the expected number of InfiniBand network interfaces are present and in UP operational state using the `ip` command with JSON output parsing.

## Requirements

- **ip**: iproute2 package with JSON output support (v4.13+)
- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox drivers

### Package Installation
```shell
# RHEL/CentOS
yum install iproute

# Ubuntu/Debian
apt-get install iproute2
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--interface-num` | Integer | 8 | Expected number of UP InfiniBand interfaces |
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
| **OK (0)** | Interface count matches expected |
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Exception during execution |
| **CRITICAL (2)** | Interface count mismatch |
| **CRITICAL (2)** | Invalid JSON output |

## Usage Examples

### Basic Interface Count Check
```shell
health_checks check-ib check-ib-interfaces \
  --interface-num 8 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Custom Interface Count
```shell
health_checks check-ib check-ib-interfaces \
  --interface-num 16 \
  --timeout 30 \
  --sink file --sink-opts filepath=/var/log/ib_interfaces.json \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-ib check-ib-interfaces \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
