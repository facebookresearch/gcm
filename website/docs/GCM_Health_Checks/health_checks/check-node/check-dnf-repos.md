# check-dnf-repos

## Overview
Validates that DNF package repositories are reachable and accessible. Ensures that package installation and system updates can proceed without repository connectivity issues.

## Requirements
- **dnf**: DNF package manager (standard on RHEL/CentOS 8+ and Fedora)
- Network access to configured repositories

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
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
| **OK (0)** | Command succeeds with output |
| **CRITICAL (2)** | Command fails |
| **CRITICAL (2)** | No output produced |

## Usage Examples

### Basic DNF Repository Check
```shell
# Verify repositories are accessible
health_checks check-node check-dnf-repos [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-node check-dnf-repos \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-node check-dnf-repos \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
