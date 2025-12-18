# service-status

## Overview
Checks if one or more systemd services are active using `systemctl is-active` command. Validates service operational status and reports CRITICAL if any service is not running.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--service` / `-s` | String | **Required** | Service name(s) to check (multiple allowed) |
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
| **OK (0)** | All requested services are active |
| **CRITICAL (2)** | One or more services are not running |

## Usage Examples

### service-status - Check Single Service
```shell
health_checks check-service service-status \
  --service slurmd \
  [CLUSTER] \
  app
```

### service-status - Check Multiple Services
```shell
health_checks check-service service-status \
  --service slurmd \
  --service sssd \
  --service chronyd \
  [CLUSTER] \
  app
```

### service-status - With Telemetry
```shell
health_checks check-service service-status \
  --service slurmd \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### service-status - Debug Mode
```shell
health_checks check-service service-status \
  --service slurmd \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
