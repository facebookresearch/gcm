# check-airstore

## Overview
Validates that Flash Array credentials are properly configured on nodes by checking the AIRStore credential count.

## Purpose
Ensures that the required number of Flash Array bulk credentials exist in `/var/airstore/cred` directory. This is essential for nodes that need to access Flash Array storage.

## Requirements

### System Requirements
- `/var/airstore/cred` directory must exist

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--expected-count-ge` | Integer | - | Minimum expected number of Flash Array credentials |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Validation Logic

1. Lists all files in `/var/airstore/cred` directory
2. Filters for files containing "bulk-cred"
3. Counts matching credential files
4. Compares actual count against `--expected-count-ge` threshold

## Exit Conditions

| Exit Code | Condition |
|--------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Credential count >= expected threshold |

## Usage Examples

### Check for at least 2 credentials
```shell
health_checks check-airstore flash-array-credential-count --expected-count-ge 2 [CLUSTER] app
```

### With custom timeout
```shell
health_checks check-airstore flash-array-credential-count --expected-count-ge 4 --timeout 30 [CLUSTER] app
```
