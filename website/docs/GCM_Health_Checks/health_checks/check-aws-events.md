# check-aws-events

## Overview
Polls the EC2 Instance Metadata Service (IMDSv2) `/latest/meta-data/events/maintenance/scheduled` endpoint for pending AWS maintenance or instance-retirement events scheduled against the local node. Surfaces them as a node condition (via NPD's exit-code translation) so operators can drain, cordon, or replace the instance ahead of AWS's enforced `NotBefore` timestamp rather than letting workloads be killed when AWS rotates the host.

The check is conservatively biased toward `OK`: any transport error, off-EC2 condition, non-2xx response, or malformed payload returns `ExitCode.OK` so a transient IMDS blip can never trigger a fleet-wide drain. Only a `200` response with a non-empty events array exits `WARN`.

## Requirements

- **EC2 instance**: The check only produces a meaningful result on AWS EC2 hosts. Off-EC2 (no IMDS), it exits `OK` with a "skipping check" message.
- **IMDSv2 reachable**: The link-local address `169.254.169.254` must be routable from the node. Any HTTP proxy env vars (`HTTP_PROXY`, `HTTPS_PROXY`) are explicitly bypassed for IMDS calls.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--imds-base-url` | String | `http://169.254.169.254` | IMDS base URL. Override only for testing. |
| `--imds-timeout` | Integer | 3 | Per-call HTTP timeout in seconds for IMDS requests. |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opt` / `-o` | Multiple | - | Sink-specific configuration (OmegaConf dot-list syntax) |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `healthchecks` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag `disable_check_aws_events` set (killswitch active) |
| **OK (0)** | No pending AWS maintenance events |
| **OK (0)** | IMDS token endpoint unreachable (off-EC2 or network blip) |
| **OK (0)** | IMDS events endpoint unreachable, returned non-200/404, or returned a malformed/non-list payload |
| **WARN (1)** | One or more pending maintenance events; message includes `Code NotBefore=... State=... EventId=...` for the first event |
| **UNKNOWN (3)** | Unexpected error before parsing |

## Usage Examples

### Basic Check
```shell
health_checks check-aws-events [CLUSTER] app
```

### With Telemetry
```shell
health_checks check-aws-events \
  --sink otel \
  --sink-opt "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode (point at a local fake IMDS)
```shell
health_checks check-aws-events \
  --imds-base-url http://127.0.0.1:9999 \
  --log-level DEBUG \
  --verbose-out \
  --sink stdout \
  [CLUSTER] \
  app
```
