# check-ethlink

## Overview
Validates Ethernet interface configuration and operational status against a node manifest. Ensures network interfaces are properly configured, operationally up, and running at expected speeds.

> Expects a file with hardware information, like [DGX_A100.json](https://github.com/facebookresearch/gcm/blob/main/gcm/tests/data/health_checks/DGX_A100.json)

**Health Check**: Ethernet Link Validation

## Manifest File Format

The manifest file defines expected network interface configuration:

```json
{
  "eth": {
    "device_name": {
      "netdev": "eth0",
      "phys": true,
      "flags": ["UP", "LOWER_UP"],
      "speed": 25000,
      "mtu": 9000
    }
  }
}
```

### Manifest Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `netdev` | String | Yes | Network interface name (e.g., "eth0", "bond0") |
| `phys` | Boolean | No | If true, check MAC address against ifcfg file |
| `flags` | List[String] | Yes | Expected interface flags |
| `speed` | Integer | No | Expected link speed in Mbps |
| `mtu` | Integer | Yes | Expected MTU size in bytes |

## Validation Logic

The check performs three sequential validations, stopping at first failure:

### 1. MAC Address Validation (`check_cfg_macaddr`)
For interfaces with `phys: true`:
1. Read configuration from `/etc/sysconfig/network-scripts/ifcfg-{netdev}`
2. Query physical MAC address via `ethtool -P {netdev}`
3. Compare `HWADDR` from config (lowercase) with actual MAC address
4. **Exit CRITICAL** if:
   - Configuration file missing
   - MAC addresses don't match

### 2. Link State Validation (`check_link_state`)
For all interfaces:
1. Query interface state via `ip -j addr`
2. Check `operstate` field is "UP"
3. Verify all expected flags are present
4. Validate MTU matches expected value
5. **Exit CRITICAL** if:
   - Interface operstate is not "UP"
   - Any expected flags are missing
6. **Exit WARN** if:
   - MTU doesn't match expected (and no other CRITICAL conditions)

### 3. Link Speed Validation (`check_link_speed`)
For interfaces with `speed` defined:
1. Read link speed from `/sys/class/net/{netdev}/speed`
2. Compare actual speed with expected speed (in Mbps)
3. **Exit WARN** if speed is lower than expected

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All checks passed |
| **OK (0)** | No ethernet interfaces in manifest |
| **WARN (1)** | Link speed lower than expected |
| **WARN (1)** | MTU mismatch (without other critical issues) |
| **WARN (1)** | Exception during check execution |
| **CRITICAL (2)** | Configuration file missing for physical interface |
| **CRITICAL (2)** | MAC address mismatch |
| **CRITICAL (2)** | Interface operstate is DOWN |
| **CRITICAL (2)** | Expected interface flags missing |

## Dependencies

### System Requirements
- `/usr/sbin/ip` command (iproute2 package)
- `/usr/sbin/ethtool` command (ethtool package)
- `/etc/sysconfig/network-scripts/ifcfg-*` configuration files (RHEL/CentOS)
- `/sys/class/net/` sysfs interface

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--manifest_file` | String | `/etc/manifest.json` | Path to node manifest file |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Usage Examples

### Basic Check (Default Manifest)
```shell
health_checks check-ethlink [CLUSTER] app
```

### Custom Manifest Location
```shell
health_checks check-ethlink --type monitor --manifest_file /opt/config/network_manifest.json [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-ethlink \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER]
  app
```
