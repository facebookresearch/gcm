# diag

## Overview
Performs comprehensive GPU diagnostics using NVIDIA Data Center GPU Manager (DCGM). Validates GPU health across deployment, integration, hardware, and stress test categories.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--diag_level` | Integer (1-4) | 1 | Diagnostic depth: 1=quick, 2=medium, 3=long, 4=extended |
| `--exclude_category` / `-x` | Multiple | [] | Skip specific test categories (can specify multiple) |
| `--host` | String | localhost | DCGM host endpoint to connect to |
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
| **OK (0)** | All diagnostic tests passed |
| **WARN (1)** | DCGM command failed to execute |
| **WARN (1)** | Test returned warning status |
| **WARN (1)** | Output parsing failed |
| **CRITICAL (2)** | One or more diagnostic tests failed |

## Usage Examples

### Basic Diagnostic
```shell
health_checks check-dcgmi diag [CLUSTER] app
```

### Exclude Specific Categories
```shell
health_checks check-dcgmi diag \
  --exclude_category "Graphics Processes" \
  --exclude_category "Persistence Mode" \
  [CLUSTER] \
  app
```

### Remote DCGM Host
```shell
health_checks check-dcgmi diag \
  --host dcgm-server.example.com \
  --timeout 180 \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-dcgmi diag \
  --diag_level 1 \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
