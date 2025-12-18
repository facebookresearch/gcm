# check-blockdev

## Overview
Validates NVMe block device health by comparing SMART data against manifest specifications.

> Expects a file with hardware information, like [DGX_A100.json](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/data/health_checks/DGX_A100.json)

## Requirements

### System Requirements
- `smartctl` from smartmontools package
- Access to `/sys/block/` filesystem
- Access to manifest file

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--manifest_file` | String | `/etc/manifest.json` | Path to hardware manifest file |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |


## Validation Logic

Performs comprehensive checks for each NVMe device listed in manifest:

### 1. Health Log Status
- Reads SMART health information log
- Verifies log is available and readable
- **CRITICAL** if health log is invalid

### 2. Device Size Validation
- Compares actual device size against manifest specification
- Uses sysfs: `/sys/block/<device>/size`
- **CRITICAL** if sizes don't match

### 3. Lifetime Usage
- Checks "Percentage Used" SMART attribute
- **CRITICAL** if > 100% (lifetime exceeded)
- **WARN** if > 80% (approaching end of life)

### 4. Spare Space Threshold
- Monitors "Available Spare" vs "Available Spare Threshold"
- **CRITICAL** if spare space < threshold

### 5. SMART Data Consistency
- Validates read/write statistics are consistent
- Checks data units read/written
- **CRITICAL** if inconsistent or negative values

### 6. Device Identification
- Verifies serial number and model information
- Cross-references with manifest expectations

## Manifest File Format

Expected JSON structure:
```json
{
  "blockdev": [
    {
      "device": "/dev/nvme0n1",
      "size_bytes": 3840755982336,
      "model": "Samsung SSD Model",
      "serial": "S12345678"
    }
  ]
}
```

## Exit Conditions

| Exit Code | Condition |
|--------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All health checks pass |
| **WARN (1)** | Lifetime usage > 80%, command failures |
| **CRITICAL (2)** | Health log invalid, size mismatch, lifetime > 100%, spare space low, bad SMART data |

## Usage Examples

### Default manifest check
```shell
health_checks check-blockdev [CLUSTER] app
```

### Custom manifest location
```shell
health_checks check-blockdev --manifest_file /etc/custom_manifest.json [CLUSTER] app
```

### With timeout
```shell
health_checks check-blockdev --manifest_file /etc/manifest.json --timeout 60 [CLUSTER] app
```
