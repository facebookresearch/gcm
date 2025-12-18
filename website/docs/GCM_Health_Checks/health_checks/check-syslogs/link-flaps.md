# link-flaps

## Overview
Detects network interface instability by scanning syslog for "Lost Carrier" messages. Classifies severity based on interface type: InfiniBand link flaps trigger CRITICAL state, Ethernet flaps trigger WARN state.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--syslog_file` | String | `/var/log/syslog` | Path to syslog file to scan |
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
| **OK (0)** | No link flaps detected |
| **WARN (1)** | Ethernet link flaps detected |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | InfiniBand link flaps detected |

## Usage Examples

### link-flaps - Basic Check
```shell
health_checks check-syslogs link-flaps [CLUSTER] app
```

### link-flaps - Custom Syslog Path
```shell
health_checks check-syslogs link-flaps \
  --syslog_file /var/log/syslog.1 \
   [CLUSTER] \
   app
```

### link-flaps - Debug Mode
```shell
health_checks check-syslogs link-flaps \
  --log-level DEBUG \
  --verbose-out \
   [CLUSTER] \
   app
```
