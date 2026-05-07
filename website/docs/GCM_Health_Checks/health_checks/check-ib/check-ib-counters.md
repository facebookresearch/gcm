# check-ib-counters

## Overview

Reads InfiniBand port error counters directly from sysfs (`/sys/class/infiniband/`) on the local node. Detects degraded fabric performance by monitoring hardware error counters that indicate cable issues, signal integrity problems, or link instability -- conditions where the link is physically up but silently dropping packets or corrupting data.

## What It Monitors

The following per-port error counters are read from sysfs:

| Counter | What It Indicates |
|---------|-------------------|
| `symbol_error` | Physical layer symbol errors (signal integrity) |
| `link_error_recovery` | Link retrained after errors (cable/connector issues) |
| `link_downed` | Link went down unexpectedly (**critical**) |
| `port_rcv_errors` | Malformed packets received |
| `port_rcv_constraint_errors` | Packets dropped due to partition/QoS violations |
| `port_xmit_discards` | Packets dropped on transmit (congestion or errors) |
| `excessive_buffer_overrun_errors` | Buffer overflow (flow control failure) |
| `local_link_integrity_errors` | Local link error threshold exceeded |

## Requirements

- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox drivers
- **sysfs**: `/sys/class/infiniband/` must be populated (standard on any node with IB)

No external tools or sudo required -- reads directly from sysfs.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--error-threshold` | Integer | 0 | Counter value threshold. Values strictly above this trigger an alert. Set to 0 to alert on any errors. |
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
| **OK (0)** | All counters at or below threshold |
| **WARN (1)** | No IB devices or counters found |
| **WARN (1)** | Error counters above threshold (non-critical counters) |
| **CRITICAL (2)** | `link_downed` above threshold |

## Usage Examples

### Basic check (alert on any non-zero errors)
```shell
health_checks check-ib check-ib-counters \
  --sink stdout \
  [CLUSTER] \
  prolog
```

### With threshold (tolerate low error counts)
```shell
health_checks check-ib check-ib-counters \
  --error-threshold 10 \
  --sink otel \
  [CLUSTER] \
  prolog
```

### Nagios mode with verbose output
```shell
health_checks check-ib check-ib-counters \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  nagios
```

## Killswitch

Disable via TOML config:
```toml
[HealthChecksFeatures]
disable_ib_port_counters = true
```
