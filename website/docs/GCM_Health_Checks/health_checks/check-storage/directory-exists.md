# directory-exists

## Overview
Validates specified directories exist on the filesystem.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--directory` / `-d` | Path | **Required** | Directory(ies) to check for existence (multiple allowed) |
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
| **OK (0)** | All directories exist |
| **CRITICAL (2)** | Directory does not exist |
| **UNKNOWN (3)** | Exception during check |

## Usage Examples

### directory-exists - Single Directory
```shell
health_checks check-storage directory-exists \
  --directory /scratch \
  [CLUSTER] \
  app
```

### directory-exists - Multiple Directories
```shell
health_checks check-storage directory-exists \
  --directory /scratch \
  --directory /data \
  --directory /models \
  [CLUSTER] \
  app
```

### directory-exists - Debug Mode
```shell
health_checks check-storage directory-exists \
  --directory /scratch \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```

### directory-exists - With Telemetry
```shell
health_checks check-storage directory-exists \
  --directory /scratch \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
