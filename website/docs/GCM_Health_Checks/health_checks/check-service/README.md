# check_service

System service and package version validation suite, plus Slurm cluster health monitoring. All checks are accessed as subcommands under the `check_service` CLI group.

## Available Health Checks

| Check | Purpose |
|-------|---------|
| [service-status](./service-status.md) | Verify systemd service status |
| [package-version](./package-version.md) | Validate RPM package versions |
| [slurmctld-count](./slurmctld-count.md) | Verify minimum slurmctld daemons are reachable |
| [node-slurm-state](./node-slurm-state.md) | Validate node can accept Slurm jobs |
| [cluster-availability](./cluster-availability.md) | Monitor percentage of nodes in unhealthy states |

## Quick Start

```shell
# Check service status
health_checks check_service service_status --cluster my_cluster --type health_check --service slurmd

# Verify package version
health_checks check_service package_version --cluster my_cluster --type health_check --package slurm --version 21.08.8-1.el8

# Controller daemon count check
health_checks check_service slurmctld_count --cluster my_cluster --type health_check --slurmctld-count 2

# Node state check
health_checks check_service node_slurm_state --cluster my_cluster --type health_check

# Cluster availability check
health_checks check_service cluster_availability --cluster my_cluster --type health_check
```
