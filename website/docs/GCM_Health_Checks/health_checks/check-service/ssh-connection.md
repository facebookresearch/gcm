# ssh-connection

## Overview
Validates SSH connectivity to specified remote hosts. Tests whether SSH connections can be established successfully to target hostaddresses.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--hostaddress` / `--host` | String | - | Hostaddress(es) to check for SSH connection (multiple allowed) |
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
| **OK (0)** | All SSH connections succeeded |
| **CRITICAL (2)** | One or more SSH connections failed |

## Usage Examples

### Check Single Host
```shell
health_checks check-service ssh-connection \
  --hostaddress controller01 \
  --timeout 30 \
  [CLUSTER] \
  app
```

### Check Multiple Hosts
```shell
health_checks check-service ssh-connection \
  --cluster my_cluster \
  --type health_check \
  --hostaddress controller01 \
  --hostaddress controller02 \
  --hostaddress controller03 \
  --timeout 30 \
  [CLUSTER] \
  app
```

### With Telemetry
```shell
health_checks check-service ssh-connection \
  --hostaddress controller01 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-service ssh-connection \
  --hostaddress controller01 \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
