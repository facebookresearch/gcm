# Health Checks Documentation

Comprehensive documentation for all GCM health checks. Health checks validate system health, hardware functionality, and configuration correctness across compute nodes.

## Overview

Health checks are organized into the following categories:

## Quick Reference

| Check | Category | Purpose |
|-------|----------|---------|
| [check-airstore](check-airstore.md) | Storage | Validates Flash Array credential configuration |
| [check-authentication](check-authentication) | Security | Verifies password status and file access permissions |
| [check-blockdev](check-blockdev.md) | Storage | Monitors NVMe device health via SMART data |
| [check-dcgmi](check-dcgmi) | GPU | NVIDIA DCGM diagnostics and NVLink validation |
| [check-ethlink](check-ethlink.md) | Network | Validates Ethernet interface configuration and state |
| [check-hca](check-hca.md) | Network | Verifies InfiniBand HCA device count |
| [check-ib](check-ib) | Network | InfiniBand link health and performance validation |
| [check-ipmitool](check-ipmitool.md) | Hardware | System Event Log (SEL) analysis for hardware errors |
| [check-nccl](check-nccl.md) | GPU | NCCL collective operation performance testing |
| [check-node](check-node) | System | Node uptime, kernel modules, and package repositories |
| [check-nvidia-smi](check-nvidia-smi) | GPU | Comprehensive GPU health validation via NVML (including clock policy drift checks) |
| [check-pci](check-pci.md) | Hardware | PCI device presence and PCIe link validation |
| [check-process](check-process) | Process | Process existence and state validation |
| [check-processor](check-processor) | CPU | CPU/processor configuration validation |
| [check-sensors](check-sensors.md) | Hardware | Fan and PSU sensor monitoring via IPMI |
| [check-service](check-service) | System | Service status and package version validation |
| [check-ssh-certs](check-ssh-certs.md) | Security | SSH certificate validation against IPA |
| [check-storage](check-storage) | Storage | Disk usage, mounts, and file system validation |
| [check-syslogs](check-syslogs) | System | System log analysis for hardware and network errors |
| [check-telemetry](check-telemetry.md) | Utility | Telemetry publishing test utility |
| [memtest](memtest.md) | GPU | GPU memory integrity testing |

## Exit Codes

All health checks follow a standard exit code convention:

| Exit Code | Description |
|-----------|--------|-------------|
| **OK (0)** | Check passed successfully |
| **WARN (1)** | Non-critical issues detected |
| **CRITICAL (2)** | Critical issues detected |
| **UNKNOWN (3)** | Check could not complete |

## Command-Line Options

Common Options:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

Check-specific options are documented in each health check's page.

### Feature Flag Disabled
If a check is disabled via feature flag, it will return OK immediately without performing validation. Check feature flag configuration if unexpected.

## Contributing

When adding new health checks:
1. Implement in [`gcm/gcm/health_checks/checks/`](https://github.com/facebookresearch/gcm/tree/main/gcm/health_checks/checks)
2. Create documentation following the format of existing checks
3. Add entry to this README in appropriate category
4. Include usage examples
5. Document all command-line options and exit conditions
