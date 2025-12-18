# check-ibstat

## Overview
Verifies InfiniBand link operational status using `ibstat` command. Checks physical link state (LinkUp) or operational state (Active) with filtering options for InfiniBand links versus all adapter ports.

## Requirements
- **InfiniBand Drivers**: Mellanox/NVIDIA OFED or inbox drivers
- **ibstat**: Part of infiniband-diags package

### Package Installation
```shell
# RHEL/CentOS
yum install infiniband-diags iproute

# Ubuntu/Debian
apt-get install infiniband-diags iproute2
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--physical-state` | Flag | True | Check 'Physical state: LinkUp' |
| `--state` | Flag | - | Check 'State: Active' (alternative to physical-state) |
| `--iblinks-only` | Flag | True | Filter only InfiniBand links |
| `--all-links` | Flag | - | Check all adapter links (alternative to iblinks-only) |
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
| **OK (0)** | All links report expected state |
| **WARN (1)** | Command execution failed |
| **WARN (1)** | Exception during execution |
| **CRITICAL (2)** | Physical state not LinkUp |
| **CRITICAL (2)** | State not Active |

## Usage Examples

### check-ibstat - Basic Physical State Check
```shell
health_checks check-ib check-ibstat \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### check-ibstat - Operational State Check
```shell
health_checks check-ib check-ibstat \
  --state \
  --iblinks-only \
  --sink stdout \
  [CLUSTER] \
  app
```

### check-ibstat - All Ports Physical State
```shell
health_checks check-ib check-ibstat \
  --physical-state \
  --all-links \
  --timeout 30 \
  --sink file --sink-opts filepath=/var/log/ibstat_check.json \
  [CLUSTER] \
  app
```

### check-ibstat - Debug Mode
```shell
health_checks check-ib check-ibstat \
  --physical-state \
  --iblinks-only \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
