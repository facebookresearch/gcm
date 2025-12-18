# check-hca

## Overview
Validates the presence and count of [Host Channel Adapters (HCAs)](https://cw.infinibandta.org/files/showcase_product/090726.192240.411.HCA-DS-WEB-052709.pdf) on InfiniBand-enabled compute nodes by querying `ibv_devinfo` and comparing against expected configuration.

## Requirements

- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox drivers
- **ibv_devinfo**: Part of libibverbs-utils package
- **HCA Hardware**: Mellanox/NVIDIA ConnectX InfiniBand adapters

### Package Installation
```shell
# RHEL/CentOS
yum install libibverbs libibverbs-utils

# Ubuntu/Debian
apt-get install libibverbs1 ibverbs-utils
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--expected-count` | Integer | **Required** | Expected number of HCAs per node |
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
| **OK (0)** | HCA count matches expected |
| **WARN (1)** | HCA count exceeds expected |
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Exception during execution |
| **CRITICAL (2)** | HCA count below expected |
| **CRITICAL (2)** | No output detected |
| **CRITICAL (2)** | No HCA found in output |

## Usage Examples

### Basic Validation
```shell
health_checks check-hca \
  --expected-count 4 \
  --sink otel --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-hca \
  --expected-count 8 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
