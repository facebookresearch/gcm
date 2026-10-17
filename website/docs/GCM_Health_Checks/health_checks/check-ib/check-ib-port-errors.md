# check-ib-port-errors

## Overview

Parses `ibdiagnet` performance-monitor output to detect InfiniBand port counter errors across the entire fabric. Unlike `check-ib-counters` (which reads per-node sysfs counters), this check analyzes cluster-wide data collected by `ibdiagnet`, including switch-side port errors that are invisible to individual compute nodes.

**This is a cluster-wide check.** Run it from a management node that has recently executed `ibdiagnet --pc`, not from every compute node.

## What It Monitors

Reads two files produced by `ibdiagnet`:

- **`ibdiagnet2.pm`** — Performance-monitor counters for every port in the fabric (hex-encoded error values)
- **`ibdiagnet2.ibnetdiscover`** — Topology discovery output, used to map switch hex GUIDs to human-readable hostnames

Tracked error types (15 counters):

| Counter | Category |
|---------|----------|
| `symbol_error_counter` | Signal integrity |
| `link_error_recovery_counter` | Link recovery events |
| `local_link_integrity_errors` | Local link threshold exceeded |
| `excessive_buffer_overrun_errors` | Buffer overflow |
| `port_rcv_errors` | Receive errors |
| `port_rcv_constraint_errors` | Partition/QoS violations |
| `port_rcv_remote_physical_errors` | Remote physical errors |
| `port_rcv_switch_relay_errors` | Switch relay errors |
| `port_xmit_constraint_errors` | Transmit constraint errors |
| `port_buffer_overrun_errors` | Buffer overruns |
| `port_dlid_mapping_errors` | DLID mapping errors |
| `port_local_physical_errors` | Local physical errors |
| `port_looping_errors` | Routing loops |
| `port_malformed_packet_errors` | Malformed packets |
| `port_vl_mapping_errors` | VL mapping errors |

## Requirements

- **ibdiagnet**: Must have been run recently (`ibdiagnet --pc`) to populate `/var/tmp/ibdiagnet2/`
- **Access**: Read access to ibdiagnet output files
- **Node**: Run from a management node, not compute nodes

### Preparing Data
```shell
# Run ibdiagnet to collect fresh port counter data
sudo ibdiagnet --pc

# Optionally clear counters first for a clean baseline
sudo ibdiagnet --pc --reset_phy_info
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--pm-file` | Path | `/var/tmp/ibdiagnet2/ibdiagnet2.pm` | Path to ibdiagnet PM file |
| `--discover-file` | Path | `/var/tmp/ibdiagnet2/ibdiagnet2.ibnetdiscover` | Path to ibnetdiscover file |
| `--error-threshold` | Integer | 0 | Only report errors exceeding this count |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--verbose-out` | Flag | False | Display detailed output |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | No port errors above threshold |
| **WARN (1)** | PM file not found or empty |
| **WARN (1)** | Error reading ibdiagnet files |
| **CRITICAL (2)** | Port errors detected above threshold |

## Usage Examples

### Basic fabric error check
```shell
health_checks check-ib check-ib-port-errors \
  --sink stdout \
  [CLUSTER] \
  app
```

### With custom ibdiagnet output location
```shell
health_checks check-ib check-ib-port-errors \
  --pm-file /var/tmp/custom/ibdiagnet2.pm \
  --discover-file /var/tmp/custom/ibdiagnet2.ibnetdiscover \
  --sink stdout \
  [CLUSTER] \
  app
```

### Only report significant errors
```shell
health_checks check-ib check-ib-port-errors \
  --error-threshold 100 \
  --sink otel \
  [CLUSTER] \
  app
```

