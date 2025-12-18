# check-telemetry

## Overview
Standalone telemetry publishing utility for health checks. Accepts health check results as command-line parameters and publishes them to configured sinks without performing validation. Used for testing telemetry pipelines and integrating external health checks.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--exit_code` | Integer | - | Health check exit code: 0=OK, 1=WARN, 2=CRITICAL, 3=UNKNOWN (required) |
| `--health-check-name` | String | - | Name of the health check (required) |
| `--node` | String | - | Hostname where check was executed (required) |
| `--msg` | String | "" | Descriptive message about the check result |
| `--job-id` | Integer | 0 | SLURM job ID associated with the check |
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
| **OK (0)** | Always exits OK regardless of telemetry success or failure |

## Usage Examples

### Basic Telemetry Test
```shell
health_checks check-telemetry \
  --exit_code 0 \
  --health-check-name test_check \
  --node node001 \
  --msg "Test passed successfully" \
  --sink stdout \
  [CLUSTER] \
  app
```
