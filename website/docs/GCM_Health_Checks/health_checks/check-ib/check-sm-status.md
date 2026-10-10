# check-sm-status

## Overview

Verifies that the InfiniBand Subnet Manager (SM) is reachable from the local node and is in the expected MASTER state. The SM is the control plane of the IB fabric -- if a node cannot reach the SM, it cannot participate in fabric routing, join new multicast groups, or recover from link events.


## What It Checks

Runs the `sminfo` command, which queries the nearest SM via the local IB port. Parses the response for:

- **Reachability**: Can the node contact the SM at all?
- **State**: Is the SM in `MASTER` state? Other states (`STANDBY`, `DISCOVERING`, `INIT`) indicate an SM failover is in progress or the fabric is not fully converged.

Example `sminfo` output:
```
sminfo: sm lid 1 lmc 0 guid 0x0011223344556677 prio 14 state 3 MASTER
```

## Requirements

- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox drivers
- **sminfo**: Part of the `infiniband-diags` package
- **Root or sudo**: `sminfo` opens a UMAD device (`/dev/infiniband/umad*`) which is `root:root 0600` by default in the Linux IB stack. Run the check via `sudo` or as root.

### Package Installation
```shell
# RHEL/CentOS
yum install infiniband-diags

# Ubuntu/Debian
apt-get install infiniband-diags
```

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
| **OK (0)** | SM reachable and in MASTER state |
| **WARN (1)** | SM reachable but not in MASTER state (e.g. STANDBY, DISCOVERING) |
| **WARN (1)** | `sminfo` output could not be parsed |
| **CRITICAL (2)** | SM unreachable (`sminfo` returned non-zero exit code) |

## Usage Examples

### Basic SM reachability check
```shell
health_checks check-ib check-sm-status \
  --sink stdout \
  [CLUSTER] \
  prolog
```

### With telemetry
```shell
health_checks check-ib check-sm-status \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  prolog
```

