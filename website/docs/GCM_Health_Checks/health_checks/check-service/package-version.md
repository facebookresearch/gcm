# package-version

## Overview
Verifies installed RPM package matches expected version using `rpm -q` command. Compares version strings in `%{VERSION}-%{RELEASE}` format and reports CRITICAL on mismatch.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--package` / `-p` | String | **Required** | Package name to check |
| `--version` / `-v` | String | **Required** | Expected version in format `%{VERSION}-%{RELEASE}` |
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
| **OK (0)** | Package version matches expected version |
| **WARN (1)** | RPM command failed to execute |
| **CRITICAL (2)** | Installed version does not match expected version |

## Usage Examples

### package-version - Basic Version Check
```shell
health_checks check-service package-version \
  --package slurm \
  --version 21.08.8-1.el8 \
  [CLUSTER] \
  app
```

### package-version - CUDA Toolkit Check
```shell
health_checks check-service package-version \
  --package cuda-toolkit \
  --version 11.8.0-1 \
  [CLUSTER] \
  app
```

### package-version - With Telemetry
```shell
health_checks check-service package-version \
  --package slurm \
  --version 21.08.8-1.el8 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### package-version - Debug Mode
```shell
health_checks check-service package-version \
  --package slurm \
  --version 21.08.8-1.el8 \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
