# file-exists

## Overview
Checks if specified files exist (or optionally do not exist).

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--file` / `-f` | Path | **Required** | File(s) to check for existence (multiple allowed) |
| `--should-not-exist` | Flag | False | Invert check - verify files do not exist |
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
| **OK (0)** | File state matches expectation |
| **CRITICAL (2)** | File state doesn't match expectation |
| **UNKNOWN (3)** | Exception during check |

## Usage Examples

### file-exists - Single File
```shell
health_checks check-storage file-exists \
  --file /etc/slurm/slurm.conf \
  [CLUSTER] \
  app
```

### file-exists - Multiple Files
```shell
health_checks check-storage file-exists \
  --file /etc/slurm/slurm.conf \
  --file /var/run/munge/munge.socket.2 \
  [CLUSTER] \
  app
```

### file-exists - Inverted Check
```shell
health_checks check-storage file-exists \
  --file /var/lock/maintenance.lock \
  --should-not-exist \
  [CLUSTER] \
  app
```

### file-exists - With Telemetry
```shell
health_checks check-storage file-exists \
  --file /etc/slurm/slurm.conf \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
