# check_pci

## Overview
Validates PCI device presence and link integrity against a hardware manifest. Ensures PCIe devices (GPUs, NICs, NVMe drives, etc.) are properly seated, detected, and operating at expected speeds and widths.

## Purpose
Detects PCIe hardware issues including:
- Missing devices (unseated cards, hardware failure)
- Degraded PCIe links (reduced speed or width)
- Topology changes affecting device enumeration
- Hardware mismatches vs. expected configuration

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

## Manifest File Format

The manifest file (`/etc/manifest.json`) contains expected hardware configuration:

```json
{
  "pci": {
    "0000:17:00.0": {
      "type": "GPU",
      "dev": "NVIDIA A100",
      "zone": "GPU",
      "slot": "GPU0",
      "link_speed": ["16 GT/s PCIe", "8 GT/s PCIe"],
      "link_width": 16,
      "topology_critical": false
    },
    "0000:65:00.0": {
      "type": "NIC",
      "dev": "Mellanox ConnectX-6",
      "zone": "Network",
      "slot": "NIC0",
      "link_speed": ["16 GT/s PCIe"],
      "link_width": 16,
      "topology_critical": true
    }
  }
}
```

### Manifest Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | String (optional) | Device category (GPU, NIC, NVMe, etc.) |
| `dev` | String | Device model/name |
| `zone` | String | Logical grouping (GPU, Network, Storage) |
| `slot` | String | Human-readable identifier |
| `link_speed` | List[String] | Acceptable PCIe speeds (Gen3, Gen4, etc.) |
| `link_width` | Integer | Expected number of PCIe lanes |
| `topology_critical` | Boolean (optional) | Stop checking if this device missing (affects enumeration) |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All devices present and healthy |
| **WARN (1)** | Manifest file not found |
| **WARN (1)** | Exception during check |
| **CRITICAL (2)** | Device missing |
| **CRITICAL (2)** | Degraded link |
| **CRITICAL (2)** | Topology-critical device missing |

## Sysfs Paths

PCIe information read from Linux sysfs:

```
/sys/class/pci_bus/{domain:bus}/device/{domain:bus:device.function}/
├── current_link_speed    # e.g., "16 GT/s PCIe" (Gen4), "8 GT/s PCIe" (Gen3)
└── current_link_width    # e.g., "16", "8", "4", "1"
```

**Example**: For PCI slot `0000:17:00.0`:
- Bus: `0000:17`
- Device path: `/sys/class/pci_bus/0000:17/device/0000:17:00.0/`

## Usage Examples

### Basic Validation
```shell
health_checks check-pci [CLUSTER] app
```

### Custom Manifest Location
```shell
health_checks -pci --manifest_file /opt/config/hw_manifest.json [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-pci \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  --verbose-out \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-pci \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
