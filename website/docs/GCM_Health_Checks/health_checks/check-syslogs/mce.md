# mce

## Overview
Detects Machine Check Exception (MCE) errors by searching dmesg for MCE-related patterns. MCE errors indicate CPU or memory hardware issues that may affect system stability.

Lines are classified by severity using pattern matching against known Linux kernel MCE log formats (source of truth: [`mce_severity.py`](https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/check_utils/mce_severity.py)):

| Severity | Patterns | Examples |
|----------|----------|----------|
| **Critical** | `[Hardware Error]`, `Machine Check Exception`, `Uncorrected error`, `Fatal error`, `Processor context corrupt` | `mce: [Hardware Error]: CPU 0: Machine Check Exception: 5 Bank 9` |
| **Warning** | `Corrected error`, `temperature above threshold`, `cpu clock throttled`, `CMCI storm` | `mce: CPU0: 1 Corrected error(s) detected. Check CMCI storm count.` |
| **Informational** | `temperature.*normal`, `CPU is offline`, `Disabling lock` | `mce: CPU0: Core temperature/speed normal` |

Unrecognized `mce:` lines default to **Warning** for safety.

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
| **OK (0)** | No MCE errors detected |
| **OK (0)** | Only informational MCE events (e.g., temperature back to normal) |
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Corrected errors or thermal throttling detected |
| **CRITICAL (2)** | Hardware errors or uncorrected MCE events detected |

## Usage Examples

### mce - Basic Check
```shell
health_checks check-syslogs mce [CLUSTER] app
```

### mce - Extended Timeout
```shell
health_checks check-syslogs mce \
  --timeout 60 \
   [CLUSTER] \
   app
```

### mce - Debug Mode
```shell
health_checks check-syslogs mce \
  --log-level DEBUG \
  --verbose-out \
   [CLUSTER] \
   app
```
