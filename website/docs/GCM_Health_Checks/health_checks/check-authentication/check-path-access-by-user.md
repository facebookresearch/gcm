# check-path-access-by-user

## Overview

Validates whether a user has read or write access to a specified path.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--user`, `-u` | String | `root` | User to check access for |
| `--path`, `-p` | String | - | File or directory path to test |
| `--operation`, `-o` | Choice | `write` | Access type: `read` or `write` |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Condition |
|--------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | User has required access permission |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | User lacks required access permission |

#### Usage Examples

```shell
# Check if root can write to /tmp
health_checks check-authentication check-path-access-by-user --path /tmp [CLUSTER] app

# Check if user can read a file
health_checks check-authentication check-path-access-by-user \
  --user appuser \
  --path /var/log/app.log \
  --operation read \
  [CLUSTER] \
  app

# Verify write access to data directory
health_checks check-authentication check-path-access-by-user \
  --user datauser \
  --path /data/processing \
  --operation write \
  [CLUSTER] \
  app
```
