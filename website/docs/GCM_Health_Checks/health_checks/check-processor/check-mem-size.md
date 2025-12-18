# check-mem-size

## Overview
Validates memory configuration by verifying the number of DIMMs and total memory size against expected values using `dmidecode`.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dimms` | Integer | Auto-detected | Expected number of memory DIMMs |
| `--total-size` | Integer | Auto-detected | Expected total memory in GB |
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
| **OK (0)** | DIMMs and memory size match |
| **WARN (1)** | dmidecode command failed |
| **CRITICAL (2)** | Configuration mismatch |

## Usage Examples

### check-mem-size - Auto-detect Configuration
```shell
health_checks check-processor check-mem-size \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-mem-size - Explicit Configuration
```shell
health_checks check-processor check-mem-size \
  --dimms 16 \
  --total-size 512 \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-mem-size - With Telemetry
```shell
health_checks check-processor check-mem-size \
  --dimms 32 \
  --total-size 1024 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-mem-size - Debug Mode
```shell
health_checks check-processor check-mem-size \
  --dimms 24 \
  --total-size 768 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
