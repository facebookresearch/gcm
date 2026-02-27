# pcie-aer

## Overview
Detects PCIe Advanced Error Reporting (AER) errors by searching dmesg for `AER.*error` patterns. PCIe AER errors can indicate GPU communication issues on the PCIe bus.

Lines are classified by severity using pattern matching against known Linux kernel PCIe AER log formats (source of truth: [`pcie_severity.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/check_utils/pcie_severity.py)):

| Severity | Patterns | Examples |
|----------|----------|----------|
| **Critical** | `Uncorrectable (Fatal)`, `can't recover` | `pcieport 0000:00:03.0: AER: Uncorrectable (Fatal) error received` |
| **Warning** | `Uncorrectable` (non-fatal) | `pcieport 0000:00:02.0: AER: Uncorrectable (Non-Fatal) error received` |
| **Informational** | `Corrected error` | `pcieport 0000:00:01.0: AER: Corrected error received: 0000:01:00.0` |

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
| **OK (0)** | No PCIe AER errors detected |
| **OK (0)** | Only corrected PCIe AER errors (hardware auto-recovered) |
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Uncorrectable non-fatal PCIe AER errors detected |
| **CRITICAL (2)** | Fatal PCIe AER errors or unrecoverable device state |

## Usage Examples

### pcie-aer - Basic Check
```shell
health_checks check-syslogs pcie-aer [CLUSTER] app
```

### pcie-aer - Extended Timeout
```shell
health_checks check-syslogs pcie-aer \
  --timeout 60 \
   [CLUSTER] \
   app
```

### pcie-aer - Debug Mode
```shell
health_checks check-syslogs pcie-aer \
  --log-level DEBUG \
  --verbose-out \
   [CLUSTER] \
   app
```
