# check-ipmitool

## Overview
Validates hardware health by reading and analyzing the System Event Log (SEL) using [`ipmitool`](https://github.com/ipmitool/ipmitool) or [`nvipmitool`](https://docs.nvidia.com/dgx/dgx-station-a100-fw-container-release-notes/ver-22-02.1.html#id7). Detects and reports critical hardware errors including power supply failures, ECC errors, PCIe errors, processor throttling, and BIOS corruption events. Automatically clears the SEL when it exceeds a configurable threshold.

## Dependencies

### System Requirements
- `ipmitool` binary installed and in PATH
- OR `nvipmitool` binary for NVIDIA-specific implementation
- IPMI kernel module loaded (`ipmi_devintf`, `ipmi_si`)
- BMC (Baseboard Management Controller) accessible
- `sudo` privileges (default, can be disabled with `--no-sudo`)

### Required Commands
```shell
# For standard IPMI
which ipmitool

# For NVIDIA implementation
which nvipmitool

# Verify IPMI devices
ls -l /dev/ipmi*
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ipmitool/--nvipmitool` | Flag | `--ipmitool` | Use `ipmitool` or `nvipmitool` binary |
| `--sudo/--no-sudo` | Flag | `--sudo` | Execute command with sudo privileges |
| `--clear_log_threshold` | Integer | 40 | Clear SEL when line count exceeds threshold |
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
| **OK (0)** | No errors detected |
| **WARN (1)** | Command failed |
| **WARN (1)** | Clear failed |
| **CRITICAL (2)** | Hardware error detected |

Critical hardware events: https://github.com/facebookresearch/gcm/blob/main/gcm/health_checks/checks/check_ipmitool.py#L102-L110

## Usage Examples

### Basic SEL Check
```shell
health_checks check-ipmitool check-sel \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Using nvipmitool Without Sudo
```shell
health_checks check-ipmitool check-sel \
  --nvipmitool \
  --no-sudo \
  --sink stdout \
  [CLUSTER] \
  app
```

### Custom Clear Threshold with Debug Logging
```shell
health_checks check-ipmitool check-sel \
  --clear_log_threshold 100 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
