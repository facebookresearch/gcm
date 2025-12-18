# mounted-directory

## Overview
Verifies specified directories are currently mounted.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--directory` / `-d` | Path | **Required** | Directory(ies) to check if mounted (multiple allowed) |
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
| **OK (0)** | Directory is mounted |
| **WARN (1)** | Mount command fails |
| **CRITICAL (2)** | Directory not mounted |

## Usage Examples

### mounted-directory - Single Directory
```shell
health_checks check-storage mounted-directory \
  --directory /mnt/nfs \
  [CLUSTER] \
  app
```

### mounted-directory - Multiple Directories
```shell
health_checks check-storage mounted-directory \
  --directory /mnt/nfs \
  --directory /mnt/lustre \
  [CLUSTER] \
  app
```

### mounted-directory - With Timeout
```shell
health_checks check-storage mounted-directory \
  --directory /mnt/nfs \
  --timeout 30 \
  [CLUSTER] \
  app
```

### mounted-directory - Debug Mode
```shell
health_checks check-storage mounted-directory \
  --directory /mnt/nfs \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
