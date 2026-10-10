# check-ufm-health

## Overview

Reads the OpenSM unhealthy-ports dump file and reports any ports that have been flagged as unhealthy. OpenSM's health manager monitors ports for various conditions and writes flagged ports to a dump file -- this check surfaces that data through GCM's standard health check interface.

**This is a cluster-wide check.** Run it from the UFM management node where `/opt/ufm/log/opensm-unhealthy-ports.dump` is populated, not from compute nodes.


## What It Monitors

OpenSM's health manager writes problematic ports to `/opt/ufm/log/opensm-unhealthy-ports.dump`. Conditions that declare a node as [unhealthy](https://docs.nvidia.com/networking/display/ufmenterpriseumv6150/unhealthy+ports+window) include:

- **REBOOT** — node rebooted more than 10 times during last 900 seconds
- **FLAPPING** — several links found in Initializing state in 5 out of 10 previous sweeps
- **UNRESPONSIVE** — port does not respond to SMPs (MAD status TIMEOUT) in 5 out of 7 previous sweeps
- **NOISY** — node sends traps 129, 130, or 131 more than 250 times with less than 60 seconds between each
- **SET_ERR** — node responds with bad status upon SET SMPs (PortInfo, SwitchInfo, VLArb, SL2VL, or Pkeys)
- **ILLEGAL** — illegal MAD fields discovered during receive_process
- **MANUAL** — manually marked as unhealthy by an operator
- **LLR** — Link Level Retransmission per-second counter exceeds threshold

The check reads the dump file and reports its contents. An empty file means no unhealthy ports.

## Requirements

- **UFM**: NVIDIA Unified Fabric Manager must be installed and running
- **Root or sudo**: `/opt/ufm/log/opensm-unhealthy-ports.dump` is owned by root. Run the check via `sudo` or as root.
- **Node**: Run from the UFM management node

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--unhealthy-ports-file` | Path | `/opt/ufm/log/opensm-unhealthy-ports.dump` | Path to OpenSM unhealthy-ports dump |
| `--truncate` / `--no-truncate` | Flag | `--no-truncate` | Truncate the dump file after reading to avoid stale alerts |
| `--preview-limit` | Integer | 20 | Maximum number of unhealthy port lines to include in the output message |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--verbose-out` | Flag | False | Display detailed output |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | No unhealthy ports (dump file empty or not found) |
| **CRITICAL (2)** | One or more unhealthy ports reported |

## Usage Examples

### Basic UFM health check
```shell
health_checks check-ib check-ufm-health \
  --sink stdout \
  [CLUSTER] \
  app
```

### With custom dump file location
```shell
health_checks check-ib check-ufm-health \
  --unhealthy-ports-file /var/log/ufm/unhealthy-ports.dump \
  --sink stdout \
  [CLUSTER] \
  app
```

### With telemetry for alerting
```shell
health_checks check-ib check-ufm-health \
  --sink otel \
  --sink-opts "log_resource_attributes={'role': 'ufm'}" \
  [CLUSTER] \
  app
```

## Deployment

This check should run on the UFM management node where the OpenSM dump file exists, not on compute nodes. It is not part of the per-node prolog/epilog pipeline.
