# check-mountpoint

## Overview
Ensures mountpoint entries in `/etc/fstab` match those in `/proc/mounts`.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mountpoint` | String | **Required** | Mountpoint pattern(s) to verify consistency (multiple allowed) |
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
| **OK (0)** | All fstab entries are mounted |
| **WARN (1)** | Command execution fails |
| **CRITICAL (2)** | Fstab entries missing from mounts |

## Usage Examples

### check-mountpoint - Single Pattern
```shell
health_checks check-storage check-mountpoint \
  --mountpoint /mnt \
  [CLUSTER] \
  app
```

### check-mountpoint - Multiple Patterns
```shell
health_checks check-storage check-mountpoint \
  --mountpoint /mnt \
  --mountpoint /data \
  [CLUSTER] \
  app
```

### check-mountpoint - With Timeout
```shell
health_checks check-storage check-mountpoint \
  --mountpoint /mnt \
  --timeout 30 \
  [CLUSTER] \
  app
```

### check-mountpoint - Debug Mode
```shell
health_checks check-storage check-mountpoint \
  --mountpoint /mnt \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
