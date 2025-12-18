# xid

## Overview
Detects NVIDIA GPU hardware errors by searching dmesg for XID (eXtended ID) error codes. Classifies errors by severity using internal XID error code database: critical XIDs trigger CRITICAL state, non-critical XIDs trigger WARN state.

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
| **OK (0)** | No XID errors found |
| **WARN (1)** | Non-critical XID errors detected |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | Critical XID errors detected |

## Usage Examples

### xid - Basic Check
```shell
health_checks check-syslogs xid [CLUSTER] app
```

### xid - Extended Timeout
```shell
health_checks check-syslogs xid \
  --timeout 60 \
   [CLUSTER] \
   app
```

### xid - Debug Mode
```shell
health_checks check-syslogs xid \
  --log-level DEBUG \
  --verbose-out \
   [CLUSTER] \
   app
```
