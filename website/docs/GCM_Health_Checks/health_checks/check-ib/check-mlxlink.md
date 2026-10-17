# check-mlxlink

## Overview

Checks InfiniBand module health using `mlxlink -m`, focusing on per-lane fault flags and DDM (Digital Diagnostic Monitoring) value ranges. Unlike `check-mlxcables` (which uses the legacy `mlxcables --DDM` flow that fails on CMIS/OSFP modules), this check works on all generations of NVIDIA HCAs including ConnectX-7 with OSFP transceivers.

This is the recommended cable health check for DGX H100/H200 fleets.

## What It Checks

For each HCA (`/dev/mst/mt*pciconf*`), runs `mlxlink -d <device> -m` and inspects:

### Critical conditions (exit code 2)
- `Module FW Fault` -- module firmware crashed
- `DataPath FW Fault` -- datapath firmware crashed
- `Tx Fault` per-lane -- TX laser/electrical failure
- `Rx LOS` / `Tx LOS` per-lane -- Loss Of Signal
- `Module State` not `Ready state`
- `DataPath state` not `DPActivated`

### Warning conditions (exit code 1)
- `Rx CDR LOL` / `Tx CDR LOL` per-lane -- Clock Data Recovery Loss Of Lock
- `Tx Adaptive EQ Fault` per-lane -- TX equalizer can't adapt
- DDM values outside the bracketed `[min..max]` range (Temperature, Voltage, Bias, Rx/Tx Power)

## Requirements

- **MFT installed**: `mlxlink` is part of NVIDIA's Mellanox Firmware Tools package
- **mst started**: Run `sudo mst start` once to expose `/dev/mst/mt*pciconf*` devices
- **Root or sudo**: `mlxlink` requires elevated privileges to access HCAs

### Setup

```shell
# Start the mst kernel modules and create /dev/mst/ device files
sudo mst start

# Verify pciconf devices are present
ls /dev/mst/mt*pciconf*
```

`mst start` is non-disruptive — it just loads kernel modules and creates device files for diagnostic tools. It does not touch the IB driver or in-flight traffic.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--critical-flags` | String (multiple) | `Module FW Fault, DataPath FW Fault, Tx Fault, Rx LOS, Tx LOS` | Per-lane fault flags that escalate to CRITICAL when nonzero |
| `--warn-flags` | String (multiple) | `Rx CDR LOL, Tx CDR LOL, Tx Adaptive EQ Fault` | Per-lane fault flags that escalate to WARN when nonzero |
| `--check-ddm-ranges` / `--no-check-ddm-ranges` | Flag | `--check-ddm-ranges` | Verify Temperature/Voltage/Bias/Power values fall within reported ranges |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--verbose-out` | Flag | False | Display detailed output |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All HCAs healthy |
| **WARN (1)** | DDM values out of range, or warn flags nonzero |
| **WARN (1)** | `mlxlink` failed for one or more HCAs |
| **CRITICAL (2)** | Any critical flag nonzero, or Module/DataPath state degraded |
| **UNKNOWN (3)** | No `/dev/mst/mt*pciconf*` devices found (mst not started) |

## Usage Examples

### Basic check
```shell
sudo health_checks check-ib check-mlxlink \
  --sink stdout \
  [CLUSTER] \
  app
```

### Skip DDM range checks (only check fault flags)
```shell
sudo health_checks check-ib check-mlxlink \
  --no-check-ddm-ranges \
  --sink stdout \
  [CLUSTER] \
  app
```

### Custom critical flag set
```shell
sudo health_checks check-ib check-mlxlink \
  --critical-flags "Module FW Fault" \
  --critical-flags "Rx LOS" \
  --sink stdout \
  [CLUSTER] \
  app
```

### With telemetry
```shell
sudo health_checks check-ib check-mlxlink \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

## Comparison with `check-mlxcables`

| | check-mlxcables | check-mlxlink |
|---|---|---|
| Tool used | `mlxcables --DDM` per device | `mlxlink -m` per HCA |
| Hardware | CX-5/CX-6 with QSFP | Any (CX-5/6/7, QSFP/OSFP) |
| Source devices | `/dev/mst/mt*cable_0` (needs `mst cable add`) | `/dev/mst/mt*pciconf*` (just `mst start`) |
| Detection method | Greps for `WARNING`/`ALARM` keywords | Per-lane fault flags + DDM range checks |
| CMIS/OSFP support | No (returns "does not support DDM") | Yes |
