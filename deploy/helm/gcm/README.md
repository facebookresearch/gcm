<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# GCM Helm Chart

A Helm chart for deploying [GCM](https://github.com/facebookresearch/gcm) on Kubernetes clusters with Slurm-managed GPU nodes.

## Prerequisites

- Kubernetes 1.26+
- Helm 3.x
- Slurm client binaries available on the host nodes
- GCM Docker image (see [docker/README.md](../../../docker/README.md))

## Install

```shell
helm install gcm deploy/helm/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set healthChecks.sink=otel \
  --set healthChecks.cluster=my-cluster
```

## Components

### Monitoring DaemonSet

Runs `gcm` on every node to collect per-node GPU and Slurm metrics. The DaemonSet mounts the host Slurm binaries so the collector can query job metadata.

### Health Checks CronJob

Runs `health_checks` on a schedule (default: every 15 minutes) to verify hardware, software, and service health.

## Configuration

See [values.yaml](values.yaml) for all configurable parameters.

| Parameter | Description | Default |
|---|---|---|
| `image.repository` | Container image repository | `ghcr.io/facebookresearch/gcm` |
| `image.tag` | Image tag (defaults to chart appVersion) | `""` |
| `monitoring.enabled` | Deploy the monitoring DaemonSet | `true` |
| `monitoring.sink` | Exporter sink for metrics | `""` |
| `monitoring.cluster` | Cluster name for metrics | `""` |
| `monitoring.interval` | Collection interval in seconds | `60` |
| `healthChecks.enabled` | Deploy the health checks CronJob | `true` |
| `healthChecks.schedule` | Cron schedule expression | `*/15 * * * *` |
| `healthChecks.sink` | Exporter sink for health checks | `""` |
| `healthChecks.cluster` | Cluster name for health checks | `""` |
| `healthChecks.concurrencyPolicy` | CronJob concurrency policy | `Forbid` |
| `podSecurityContext.runAsNonRoot` | Enforce non-root execution | `true` |

## Security

The chart enforces security best practices by default:

- **Non-root execution**: All containers run as UID 65532
- **Read-only root filesystem**: Writable `/tmp` backed by `emptyDir`
- **Dropped capabilities**: All Linux capabilities are dropped
- **No privilege escalation**: `allowPrivilegeEscalation: false`

## Testing

Lint the chart:

```shell
helm lint deploy/helm/gcm
```

Render templates locally:

```shell
helm template my-release deploy/helm/gcm \
  --set monitoring.sink=stdout \
  --set monitoring.cluster=test
```

Run Helm tests after install:

```shell
helm test my-release
```
