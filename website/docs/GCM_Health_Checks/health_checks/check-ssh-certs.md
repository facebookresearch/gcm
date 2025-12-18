# check-ssh-certs

## Overview
Validates SSH host certificates by comparing registered fingerprints in IPA (Identity Policy Audit) against actual certificates retrieved directly from the SSH service. Ensures host key integrity and proper registration.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | String | - | Hostname to check SSH certificates against IPA |
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
| **OK (0)** | All IPA-registered certificates found in SSH service |
| **CRITICAL (2)** | Host not found/registered in IPA |
| **CRITICAL (2)** | No certificates found in IPA for host |
| **CRITICAL (2)** | IPA-registered certificates missing from SSH service |
| **CRITICAL (2)** | Cannot retrieve certificates from SSH service |
| **CRITICAL (2)** | Timeout retrieving SSH certificates |
| **UNKNOWN (3)** | IPA service error or unresponsive |
| **UNKNOWN (3)** | Timeout querying IPA |

## Usage Examples

### Basic Certificate Validation
```shell
health_checks check-ssh-certs \
  --host node001.example.com \
  [CLUSTER] \
  app
```

### With Telemetry
```shell
health_checks check-ssh-certs \
  --host node001.example.com \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-ssh-certs \
  --host node001.example.com \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
