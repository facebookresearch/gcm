# check-node

Node-level health checks suite for system uptime, kernel modules, and DNF repository validation.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [uptime](./uptime.md) | System uptime validation | Detect recent reboots with configurable threshold |
| [check-module](./check-module.md) | Kernel module validation | Verify required drivers (NVIDIA, InfiniBand) are loaded |
| [check-dnf-repos](./check-dnf-repos.md) | Repository connectivity | Ensure DNF package repositories are accessible |

## Quick Start

```shell
# Check node uptime
health_checks check-node uptime my_cluster app

# Verify kernel modules are loaded
health_checks check-node check-module --module nvidia my_cluster app

# Validate DNF repositories
health_checks check-node check-dnf-repos my_cluster app
```
