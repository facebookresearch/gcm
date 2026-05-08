# check-mlxcables

## Overview

Checks InfiniBand cable transceiver health using Mellanox DDM (Digital Diagnostic Monitoring) data. Queries each cable's optical diagnostics -- temperature, voltage, TX/RX power, and bias current -- to detect degraded or failing cables before they cause link errors or training interruptions.

DDM warnings and alarms are early indicators of cable degradation. A cable with DDM warnings may still pass link-state checks (`check-ibstat`, `check-iblink`) but could be approaching failure or already causing intermittent errors visible in port counters.

## What It Monitors

The `mlxcables --DDM` command reports per-transceiver diagnostics:

| Metric | What It Indicates |
|--------|-------------------|
| Temperature | Transceiver operating temperature (overheating = degradation) |
| Voltage | Supply voltage (out-of-spec = hardware issue) |
| TX Power | Transmit optical power (low = dirty connector or failing laser) |
| RX Power | Receive optical power (low = fiber bend, dirty connector, or far-end issue) |
| Bias Current | Laser bias current (high = laser aging) |

Each metric can report `OK`, `WARNING` (approaching limits), or `ALARM` (out of specification).

## Requirements

- **Mellanox Firmware Tools (MFT)**: Provides the `mlxcables` command
- **MST kernel module**: Must be loaded (provides `/dev/mst/` device nodes)
- **Cable devices**: At least one `/dev/mst/mt*cable_0` device must exist

### Setup
```shell
# Load MST kernel module
mst start

# Verify cable devices exist
ls /dev/mst/mt*cable_0
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--timeout` | Integer | 300 | Command execution timeout in seconds per cable |
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
| **OK (0)** | All cables report healthy DDM readings |
| **WARN (1)** | DDM WARNING or ALARM detected on one or more cables |
| **WARN (1)** | `mlxcables` command failed for a cable |
| **UNKNOWN (3)** | No cable devices found (`/dev/mst/mt*cable_0` empty) |

## Usage Examples

### Basic cable health check
```shell
health_checks check-ib check-mlxcables \
  --sink stdout \
  [CLUSTER] \
  prolog
```

### With telemetry
```shell
health_checks check-ib check-mlxcables \
  --sink otel \
  --sink-opts "log_resource_attributes={'cluster': 'my_cluster'}" \
  [CLUSTER] \
  prolog
```

### Verbose debug mode
```shell
health_checks check-ib check-mlxcables \
  --verbose-out \
  --log-level DEBUG \
  --sink stdout \
  [CLUSTER] \
  app
```

## Killswitch

Disable via TOML config:
```toml
[HealthChecksFeatures]
disable_check_ib_cable_ddm = true
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `UNKNOWN: No IB cable devices found` | MST module not loaded | Run `mst start` |
| `WARN: mlxcables failed` | MFT not installed or permission denied | Install MFT, check sudo config |
| `WARN: DDM WARNING` on temperature | Insufficient airflow or high ambient temp | Check datacenter cooling |
| `WARN: DDM ALARM` on RX power | Dirty connector or damaged fiber | Clean or replace cable |
