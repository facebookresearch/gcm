<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# GCM Helm Chart

A Helm chart for deploying [GCM](https://github.com/facebookresearch/gcm) on Kubernetes clusters with GPU nodes.

## Prerequisites

- Kubernetes 1.26+
- Helm 3.x
- NVIDIA GPU drivers and container runtime on GPU nodes
- GCM Docker image (see [docker/README.md](../../../docker/README.md))
- NPD-GCM Docker image for health checks (see [docker/README.md](../../../docker/README.md))

## Install

```shell
helm install gcm deploy/helm/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set healthChecks.cluster=my-cluster \
  --set healthChecks.sink=otel
```

## Components

### Monitoring DaemonSet

Runs `gcm nvml_monitor` on every GPU node to collect per-device GPU metrics via NVML:

- **Per-GPU**: utilization, memory usage, temperature, power draw, ECC retired pages
- **Per-GPU job association**: Slurm job ID, user, partition, and resource allocation (read from `/proc/<pid>/environ` of GPU compute processes)
- **Host-level**: min/max/avg GPU utilization, RAM utilization

The DaemonSet runs as root with `hostPID: true` so it can read the environment of GPU processes to associate metrics with Slurm jobs. It uses `NVIDIA_VISIBLE_DEVICES=all` for GPU access without reserving any GPU resources.

### Health Checks DaemonSet (NPD-GCM)

Runs [Node Problem Detector](https://github.com/kubernetes/node-problem-detector) with GCM health checks as custom plugin monitors on every GPU node. NPD manages scheduling, retries, and exposes results as Kubernetes node conditions and Prometheus metrics.

The DaemonSet runs 6 health checks every 5 minutes (configurable):

| Check | Description | NPD Condition |
|-------|-------------|---------------|
| XID Errors | Scans syslogs for NVIDIA XID errors | `XidErrorsProblem` |
| ECC Errors | Checks uncorrected/corrected ECC counters | `SmiEccProblem` |
| GPU Disconnected | Verifies expected GPU count is visible | `SmiDisconnectedProblem` |
| Zombie Processes | Detects zombie GPU processes | `ProcZombieProblem` |
| DCGM NVLink Status | Checks NVLink health via DCGM | `DcgmiNvlinkStatusProblem` |
| DCGM Diag Level 1 | Runs DCGM level 1 diagnostics | `DcgmiDiagProblem` |

## Configuration

See [values.yaml](values.yaml) for all configurable parameters.

| Parameter | Description | Default |
|---|---|---|
| `image.repository` | Monitoring container image | `ghcr.io/facebookresearch/gcm` |
| `image.tag` | Image tag (defaults to chart appVersion) | `""` |
| `monitoring.enabled` | Deploy the monitoring DaemonSet | `true` |
| `monitoring.sink` | Exporter sink for metrics | `""` |
| `monitoring.cluster` | Cluster name for metrics | `""` |
| `monitoring.interval` | Collection interval in seconds | `60` |
| `healthChecks.enabled` | Deploy the NPD health checks DaemonSet | `true` |
| `healthChecks.image.repository` | NPD-GCM combined image | `ghcr.io/facebookresearch/gcm-npd` |
| `healthChecks.image.tag` | NPD-GCM image tag | `""` |
| `healthChecks.cluster` | Cluster name for health checks | `""` |
| `healthChecks.sink` | Sink for health check results | `"stdout"` |
| `healthChecks.invokeInterval` | Check interval in seconds | `300` |
| `healthChecks.timeout` | Check timeout in seconds | `120` |
| `healthChecks.concurrency` | Max concurrent checks | `3` |
| `healthChecks.gpuCount` | Expected GPU count per node (for gpu_num check) | `8` |
| `healthChecks.prometheus.port` | Prometheus metrics port | `20257` |

## Security

Both components require elevated privileges to access GPU hardware and host processes:

- **Monitoring DaemonSet**: Runs as root (UID 0) with `hostPID: true`. Root is needed to read `/proc/<pid>/environ` of GPU compute processes for Slurm job association. `hostPID` is needed because NVML reports GPU process PIDs in the host PID namespace. GPU metrics (utilization, temperature, etc.) are collected via NVML, which requires access to the NVIDIA device files.
- **Health Checks DaemonSet**: Runs as **privileged** with `hostPID` and `hostNetwork` enabled. GPU health checks need direct access to GPU devices, host PCI topology, syslog files, DCGM diagnostics, and host process visibility. The health checks DaemonSet has its own dedicated ServiceAccount with minimal RBAC permissions (node status patching for NPD conditions).

Both DaemonSets tolerate `nvidia.com/gpu` taints by default to ensure they schedule on GPU nodes.

## Building the NPD Image

The health checks DaemonSet uses a combined NPD+GCM image. Build it after building the base GCM image:

```shell
# Build the base GCM image first
docker build -f docker/Dockerfile -t gcm:latest .

# Build the NPD-GCM combined image
docker build -f docker/Dockerfile.npd -t gcm-npd:latest .
```

## Testing

Lint the chart:

```shell
helm lint deploy/helm/gcm
```

Render templates locally:

```shell
helm template my-release deploy/helm/gcm \
  --set monitoring.sink=stdout \
  --set monitoring.cluster=test \
  --set healthChecks.cluster=test
```

Run Helm tests after install:

```shell
helm test my-release
```
