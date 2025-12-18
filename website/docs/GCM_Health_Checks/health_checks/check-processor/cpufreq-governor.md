# cpufreq-governor

## Overview
Verifies that all CPU cores use the same frequency governor and that it matches the expected setting.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--governor` | String | performance | Required CPU frequency governor |
| `--sys_freq_file` | String | `/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` | File glob pattern to read governor |
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
| **OK (0)** | All CPUs use expected governor |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Governor mismatch |

## Usage Examples

### cpufreq-governor - Performance Governor Check
```shell
health_checks check-processor cpufreq-governor \
  --sink stdout \
  [CLUSTER] \
  app
```

### cpufreq-governor - Powersave Governor Check
```shell
health_checks check-processor cpufreq-governor \
  --governor powersave \
  --sink stdout \
  [CLUSTER] \
  app
```

### cpufreq-governor - Custom Sysfs Path
```shell
health_checks check-processor cpufreq-governor \
  --governor ondemand \
  --sys_freq_file /sys/devices/system/cpu/cpu[0-7]/cpufreq/scaling_governor \
  --sink stdout \
  [CLUSTER] \
  app
```

### cpufreq-governor - Debug Mode
```shell
health_checks check-processor cpufreq-governor \
  --governor performance \
  --log-level DEBUG \
  --verbose-out \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
