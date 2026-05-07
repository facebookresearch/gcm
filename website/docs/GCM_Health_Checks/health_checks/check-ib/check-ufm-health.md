# check-ufm-health

## Overview

Reads the OpenSM unhealthy-ports dump file and reports any ports that have been flagged as unhealthy. OpenSM's health manager monitors ports for various conditions and writes flagged ports to a dump file -- this check surfaces that data through GCM's standard health check interface.

**This is a cluster-wide check.** Run it from the UFM management node where `/opt/ufm/log/opensm-unhealthy-ports.dump` is populated, not from compute nodes.

## What It Monitors

OpenSM's health manager writes problematic ports to `/opt/ufm/log/opensm-unhealthy-ports.dump`. Conditions tracked include:

- REBOOT — nodes rebooting too frequently
- FLAPPING — link going up/down repeatedly
- UNRESPONSIVE — ports not responding to SM sweeps
- NOISY — ports generating excessive traps
- SET_ERR — ports returning errors on Set operations
- ILLEGAL — ports returning illegal SMP responses

The check reads the dump file and reports its contents. An empty file means no unhealthy ports.

## Requirements

- **UFM**: NVIDIA Unified Fabric Manager must be installed and running
- **Access**: Read access to `/opt/ufm/log/opensm-unhealthy-ports.dump`
- **Node**: Run from the UFM management node

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--unhealthy-ports-file` | Path | `/opt/ufm/log/opensm-unhealthy-ports.dump` | Path to OpenSM unhealthy-ports dump |
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

## Killswitch

```toml
[HealthChecksFeatures]
disable_ib_ufm_health = true
```

## Deployment

This check should run on the UFM management node where the OpenSM dump file exists, not on compute nodes. It is not part of the per-node prolog/epilog pipeline.
