# check-ib

InfiniBand network validation suite with health checks for different validation scenarios.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [check-ibstat](./check-ibstat.md) | Link state validation | Quick verification using `ibstat` - no manifest required |
| [check-ib-interfaces](./check-ib-interfaces.md) | Interface count validation | Verify expected number of UP interfaces using `ip` command |
| [check-iblink](./check-iblink.md) | Comprehensive validation | Full hardware validation with firmware/rate checks against manifest |

## Quick Start

```shell
# Link state check
health_checks check-ib check-ibstat [CLUSTER] app

# Interface count check
health_checks check-ib check-ib-interfaces --interface-num 8 [CLUSTER] app

# Full validation with manifest
health_checks check-ib check-iblink --manifest_file /etc/manifest.json [CLUSTER] app
```
