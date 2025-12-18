# check-iblink

## Overview
Validates InfiniBand link health by comparing runtime link state from sysfs against node configuration manifest, detecting hardware issues, link degradation, firmware mismatches, and binding problems.

> Expects a file with hardware information, like [DGX_A100.json](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/data/health_checks/DGX_A100.json)

## Requirements

- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox kernel drivers
- **Sysfs**: Kernel sysfs mounted at `/sys`
- **Manifest File**: Valid JSON configuration at specified path
- **HCA Hardware**: Mellanox/NVIDIA ConnectX adapters

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--manifest_file` | String | `/etc/manifest.json` | Path to node configuration manifest |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Manifest Format

### Expected Structure
```json
{
  "pci": {
    "0000:17:00.0": {
      "slot": "slot0",
      "dev": "ib0",
      "type": "ib"
    }
  },
  "ib": {
    "link_rate": "200 Gb/sec (4X HDR)",
    "firmware_version": ["20.28.1002", "20.28.1010"],
    "interfaces": {
      "ib0": {
        "mlx": "mlx5_0",
        "desc": "Mellanox ConnectX-6"
      }
    }
  }
}
```

## Validation Logic

### Data Collection
For each InfiniBand PCI device:
1. **Read from sysfs**:
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/node_desc` - Device description
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/fw_ver` - Firmware version
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/ports/1/phys_state` - Physical state
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/ports/1/state` - Link state
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/ports/1/link_layer` - Protocol layer
   - `/sys/bus/pci/devices/{pci_id}/infiniband/{mlx}/ports/1/rate` - Link rate
   - `/sys/bus/pci/devices/{pci_id}/net/{ibdev}/operstate` - Network operational state

2. **Compare against manifest**: Validate each attribute against expected values

### Issue Classification

#### Critical Issues (Exit Code 2)
| Issue | Description | Example |
|-------|-------------|---------|
| `MISBIND` | PCI slot bound to incorrect IB interface | `slot0 is bound to ib1, expected ib0` |
| `MLX5_MISMATCH` | IB netdev and mlx5 device don't match | `ib0 is bound to mlx5_1, expected mlx5_0` |
| `MLX5_PROTOCOL_MISMATCH` | Port not in InfiniBand mode | `ib0 is not presenting as an InfiniBand link` |
| `LINK_RATE_MISMATCH` | Link speed degraded | `ib0 has degraded link 100 Gb/sec` |
| `LINK_NOT_UP` | Physical link down | `ib0 is not up, link state is 1: DOWN` |
| `LINK_BAD_STATE` | Link up but not ACTIVE | `ib0 is not up, link state is 3: ARMED` |
| `LINK_OPERSTATE_DOWN` | Netdev down despite IB ACTIVE | `ib0 is ACTIVE, but the logical interface is down` |

#### Warning Issues (Exit Code 1)
| Issue | Description | Example |
|-------|-------------|---------|
| `LINK_IN_INIT` | Link in initialization state | `ib0 is not up, link state is 2: INIT` |
| `FIRMWARE_MISMATCH` | Firmware version unexpected | `ib0 has fw version 20.27.1000, expected [20.28.1002]` |

### Aggregation
- Collects issues across all InfiniBand links
- Exit code determined by most severe issue found
- Output includes summary: `up: {count}, down: {count}`

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All links healthy |
| **WARN (1)** | Warning-level issues only |
| **WARN (1)** | Manifest file read failure |
| **CRITICAL (2)** | Any critical issue present |

## Usage Examples

### Basic Validation
```shell
health_checks check-ib check-iblink \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Custom Manifest Location
```shell
health_checks check-ib check-iblink \
  --manifest_file /opt/config/node_manifest.json \
  --sink file --sink-opts filepath=/var/log/iblink_check.json \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-ib check-iblink \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
