# pcie-aer

## Overview
Detects PCIe Advanced Error Reporting (AER) errors by searching dmesg for `AER.*error` patterns. PCIe AER errors can indicate GPU communication issues on the PCIe bus. Distinguishes between correctable and uncorrectable errors for severity classification.

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
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Corrected PCIe AER errors detected |
| **CRITICAL (2)** | Uncorrectable PCIe AER errors detected |

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
