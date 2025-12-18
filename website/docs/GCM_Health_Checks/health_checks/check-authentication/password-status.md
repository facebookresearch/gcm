# password-status

## Overview
Authentication and user access validation checks for verifying password status and file system permissions.

## password-status

Checks if a user's password status matches expected configuration using `passwd -S`.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--user`, `-u` | String | `root` | User account to check |
| `--status`, `-s` | String | `PS` | Expected password status code |
| `--sudo` / `--no-sudo` | Flag | `True` | Execute command with/without sudo |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Password Status Codes
- **PS**: Password set
- **LK**: Password locked
- **NP**: No password
- **L**: Password locked (alternative format)

## Exit Conditions

| Exit Code | Condition |
|--------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** |  Password status matches expected value |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Password status does not match expected value |

## Usage Examples

```shell
# Check root password is set
health_checks check-authentication password-status [CLUSTER] app

# Check specific user without sudo
health_checks check-authentication password-status --user myuser --no-sudo [CLUSTER] app

# Verify password is locked
health_checks check-authentication password-status --user backup --status LK [CLUSTER] app
```
