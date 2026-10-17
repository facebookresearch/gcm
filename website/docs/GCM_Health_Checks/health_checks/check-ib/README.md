# check-ib

InfiniBand network validation suite with health checks covering link state, hardware configuration, fabric performance, and cable health.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [check-ibstat](./check-ibstat.md) | Link state validation | Quick verification using `ibstat` -- no manifest required |
| [check-ib-interfaces](./check-ib-interfaces.md) | Interface count validation | Verify expected number of UP interfaces using `ip` command |
| [check-iblink](./check-iblink.md) | Comprehensive validation | Full hardware validation with firmware/rate checks against manifest |
| [check-ib-counters](./check-ib-counters.md) | Port error counters | Detect degraded links via sysfs error counters |
| [check-mlxcables](./check-mlxcables.md) | Cable DDM diagnostics | Transceiver health (temperature, power, voltage) via `mlxcables` (CX-5/6 with QSFP) |
| [check-mlxlink](./check-mlxlink.md) | Module health & DDM | Per-lane fault flags + DDM range checks via `mlxlink` (any HCA, including CX-7/OSFP) |
| [check-sm-status](./check-sm-status.md) | Subnet Manager reachability | Verify SM is reachable and in MASTER state via `sminfo` |
| [check-ib-port-errors](./check-ib-port-errors.md) | Fabric-wide port errors | Parse ibdiagnet output for switch/port errors *(cluster-wide)* |
| [check-ufm-health](./check-ufm-health.md) | OpenSM unhealthy ports | Read OpenSM's unhealthy-ports dump *(cluster-wide)* |

## Quick Start

```shell
# Link state check
health_checks check-ib check-ibstat [CLUSTER] app

# Interface count check
health_checks check-ib check-ib-interfaces --interface-num 8 [CLUSTER] app

# Full validation with manifest
health_checks check-ib check-iblink --manifest_file /etc/manifest.json [CLUSTER] app

# Port error counters (alert on any non-zero)
health_checks check-ib check-ib-counters [CLUSTER] prolog

# Cable transceiver health
health_checks check-ib check-mlxcables [CLUSTER] prolog

# Module health & DDM (preferred for CX-7/OSFP)
health_checks check-ib check-mlxlink [CLUSTER] prolog

# Subnet Manager reachability
health_checks check-ib check-sm-status [CLUSTER] prolog

# Fabric-wide port errors (run from management node)
health_checks check-ib check-ib-port-errors [CLUSTER] app

# OpenSM unhealthy ports (run from UFM node)
health_checks check-ib check-ufm-health [CLUSTER] app
```

