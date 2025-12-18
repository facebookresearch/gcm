# check-syslogs

System log analysis tool that detects hardware and network errors by searching for critical patterns in dmesg and syslog files.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [link-flaps](./link-flaps.md) | Network link stability | Detect InfiniBand and Ethernet link flaps |
| [xid](./xid.md) | GPU error detection | Identify NVIDIA XID hardware errors |
| [io-errors](./io-errors.md) | Storage health validation | Detect NVMe I/O errors |

## Quick Start

```shell
# Link flap check
health_checks check-syslogs link-flaps [CLUSTER] app

# XID error check
health_checks check-syslogs xid [CLUSTER] app

# I/O error check
health_checks check-syslogs io-errors [CLUSTER] app
```
