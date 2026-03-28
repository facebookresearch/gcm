# check-example

> **Template**: Copy this file and rename it to `check-<your_check>.md` when adding a new health check.

## Overview

_Brief description of what this check monitors and why it matters for cluster health._

## Requirements

_List any external tools, packages, or hardware needed. Remove this section if there are no special requirements._

- **Tool Name**: Description of the tool
- **Package**: `apt-get install package-name` or `yum install package-name`

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--your-option` | String | - | _Description of check-specific option_ |
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
| **OK (0)** | _Normal condition — no errors detected_ |
| **WARN (1)** | _Warning condition_ |
| **WARN (1)** | Command execution failed |
| **CRITICAL (2)** | _Critical condition_ |
| **UNKNOWN (3)** | Unexpected error before parsing |

## Usage Examples

### Basic Check
```shell
health_checks check-example [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-example \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-example \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
