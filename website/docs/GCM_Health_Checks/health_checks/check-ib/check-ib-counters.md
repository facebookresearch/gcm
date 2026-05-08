# check-ib-counters

## Overview
Monitors InfiniBand port error and throughput counters via sysfs, detecting runtime fabric degradation that silently hurts distributed training throughput (NCCL AllReduce, FSDP, etc.). This is the runtime complement to `check-iblink`: where `check-iblink` validates link *presence*, `check-ib-counters` detects performance-degrading conditions on active links.

## Requirements

- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox kernel drivers
- **Sysfs**: Kernel sysfs mounted at `/sys` with counters at `/sys/class/infiniband/{device}/ports/{port}/counters/`

## Monitored Counters

### Error Counters
| Counter | Description |
|---------|-------------|
| `symbol_error` | Physical layer symbol errors |
| `link_error_recovery` | Link error recovery events |
| `link_downed` | Link down transitions |
| `port_rcv_errors` | Malformed packets received |
| `port_rcv_remote_physical_errors` | Remote physical receive errors |
| `port_rcv_switch_relay_errors` | Switch relay errors on receive path |
| `port_xmit_discards` | Outbound packets discarded |
| `port_xmit_constraint_errors` | Transmit constraint violations |
| `port_rcv_constraint_errors` | Receive constraint violations |
| `local_link_integrity_errors` | Local link integrity failures |
| `excessive_buffer_overrun_errors` | Buffer overrun events |
| `VL15_dropped` | Dropped VL15 (management) packets |

### Throughput Counters (informational)
| Counter | Description |
|---------|-------------|
| `port_xmit_data` | Total data transmitted |
| `port_rcv_data` | Total data received |
| `port_xmit_packets` | Total packets transmitted |
| `port_rcv_packets` | Total packets received |

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--warn-threshold` | Integer | 0 | Total error count above which the check returns WARNING |
| `--crit-threshold` | Integer | 100 | Total error count above which the check returns CRITICAL |
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
| **OK (0)** | All error counters within thresholds |
| **WARN (1)** | No IB ports discovered |
| **WARN (1)** | Total errors exceed `--warn-threshold` |
| **CRITICAL (2)** | Total errors exceed `--crit-threshold` |

## Usage Examples

### Basic Check
```shell
health_checks check-ib check-ib-counters [CLUSTER] app
```

### With Custom Thresholds
```shell
health_checks check-ib check-ib-counters \
  --warn-threshold 10 \
  --crit-threshold 500 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-ib check-ib-counters \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
