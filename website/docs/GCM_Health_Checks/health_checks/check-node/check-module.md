# check-module

## Overview
Verifies that specified kernel modules are loaded on the system. Critical for ensuring required drivers (e.g., NVIDIA GPU drivers, InfiniBand modules) are available before workload execution.

## Requirements
- Linux

### Commands Used
```shell
lsmod | grep {module_name} | wc -l
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--module` / `-m` | String | **Required** | Module name(s) to check (can be specified multiple times) |
| `--mod_count` | Integer | 1 | Expected occurrence count in `lsmod` output |
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
| **OK (0)** | All modules appear >= expected count |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Any module count < expected |

## Usage Examples

### Single Module Check
```shell
# Check if nvidia module is loaded
health_checks check-node check-module \
  --module nvidia \
  [CLUSTER] \
  app
```

### Multiple Modules
```shell
# Check multiple GPU-related modules
health_checks check-node check-module \
  --module nvidia \
  --module nvidia_uvm \
  --module nvidia_drm \
  [CLUSTER] \
  app
```

### With Custom Count Threshold
```shell
# Expect 8 instances of ib_core module
health_checks check-node check-module \
  --module ib_core \
  --mod_count 8 \
  [CLUSTER] \
  app
```

### Multiple Modules with Different Counts
```shell
# Check modules with specific counts
health_checks check-node check-module \
  --module nvidia --mod_count 8 \
  --module ib_core --mod_count 1 \
  [CLUSTER] \
  app
```

### With Telemetry
```shell
health_checks check-node check-module \
  --module nvidia \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  --verbose-out \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-node check-module \
  --module nvidia \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
