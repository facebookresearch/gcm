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

Monitoring and health checks are independent — you can deploy either or both:

```shell
# Health checks only
helm install gcm deploy/helm/gcm \
  --set monitoring.enabled=false \
  --set healthChecks.cluster=my-cluster

# Monitoring only
helm install gcm deploy/helm/gcm \
  --set healthChecks.enabled=false \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

## Components

### Monitoring DaemonSet

Runs `gcm nvml_monitor` on every GPU node to collect per-device GPU metrics via NVML:

- **Per-GPU**: utilization, memory usage, temperature, power draw, ECC retired pages
- **Per-GPU job association**: Slurm job ID, user, partition, and resource allocation (read from `/proc/<pid>/environ` of GPU compute processes)
- **Host-level**: min/max/avg GPU utilization, RAM utilization

The DaemonSet runs as root with `hostPID: true` so it can read the environment of GPU processes to associate metrics with Slurm jobs. It uses `NVIDIA_VISIBLE_DEVICES=all` for GPU access without reserving any GPU resources.

### Health Checks DaemonSet (NPD-GCM)

Runs [Node Problem Detector](https://github.com/kubernetes/node-problem-detector) with GCM health checks as custom plugin monitors on every GPU node. NPD and GCM health checks run together in a single pod:

```
DaemonSet (one per node, controlled by nodeSelector/tolerations)
  └── Pod
       └── Container: node-problem-detector (NPD)
            ├── Invokes: health_checks check-syslogs xid ...
            ├── Invokes: health_checks check-nvidia-smi ...
            ├── Invokes: health_checks check-dcgmi ...
            └── ...
```

NPD is the scheduler — it runs each GCM health check as a subprocess at a configurable interval, manages retries and concurrency, and reports results as Kubernetes node conditions and Prometheus metrics. GCM `health_checks` does the actual GPU inspection.

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

See [values.yaml](values.yaml) for all configurable parameters. The key ones to set:

| Parameter | Description | Default |
|---|---|---|
| `monitoring.enabled` | Deploy the monitoring DaemonSet | `true` |
| `monitoring.sink` | Exporter sink for metrics | `""` |
| `monitoring.cluster` | Cluster name for metrics | `""` |
| `healthChecks.enabled` | Deploy the NPD health checks DaemonSet | `true` |
| `healthChecks.cluster` | Cluster name for health checks | `""` |
| `healthChecks.sink` | Sink for health check results | `"stdout"` |
| `healthChecks.gpuCount` | Expected GPU count per node | `8` |

### Sinks

The `sink` parameter controls where metrics and health check results are sent. Run `gcm nvml_monitor --help` or `health_checks --help` to see all available sinks and their options.

Sink-specific options can be passed via `monitoring.extraArgs`:

The otel sink supports standard `OTEL_EXPORTER_*` environment variables.

```shell
# Monitoring: send GPU metrics to an OpenTelemetry collector
helm install gcm deploy/helm/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set monitoring.extraArgs[0]=-o \
  --set monitoring.extraArgs[1]=otel_endpoint=http://otel-collector:4318

# Health checks: send results to an OpenTelemetry collector
# Set OTEL_EXPORTER_OTLP_ENDPOINT in the pod environment or
# configure it in your cluster's OTel setup.
helm install gcm deploy/helm/gcm \
  --set healthChecks.sink=otel \
  --set healthChecks.cluster=my-cluster
```

Run `gcm nvml_monitor --help` or `health_checks --help` to see all sinks and their options.

## Node Scheduling

By default, both DaemonSets tolerate `nvidia.com/gpu` taints and schedule on **all** nodes. This works for clusters where the NVIDIA device plugin taints GPU nodes.

For clusters that use **labels** instead of taints to identify GPU nodes, use `nodeSelector` to restrict scheduling:

```shell
helm install gcm deploy/helm/gcm \
  --set monitoring.nodeSelector."nvidia\.com/gpu\.present"=true \
  --set healthChecks.nodeSelector."nvidia\.com/gpu\.present"=true
```

For clusters with **custom taints** on GPU nodes, add the corresponding tolerations:

```yaml
# values.yaml
monitoring:
  tolerations:
    - key: "nvidia.com/gpu"
      operator: Exists
    - key: "dedicated"
      value: "gpu-workload"
      effect: "NoSchedule"
healthChecks:
  tolerations:
    - key: "nvidia.com/gpu"
      operator: Exists
    - key: "dedicated"
      value: "gpu-workload"
      effect: "NoSchedule"
```

## Security

Both components require elevated privileges to access GPU hardware and host processes:

- **Monitoring DaemonSet**: Runs as root (UID 0) with `hostPID: true`. Root is needed to read `/proc/<pid>/environ` of GPU compute processes for Slurm job association. `hostPID` is needed because NVML reports GPU process PIDs in the host PID namespace. GPU metrics (utilization, temperature, etc.) are collected via NVML, which requires access to the NVIDIA device files.
- **Health Checks DaemonSet**: Runs as **privileged** with `hostPID` and `hostNetwork` enabled. GPU health checks need direct access to GPU devices, host PCI topology, syslog files, DCGM diagnostics, and host process visibility. The health checks DaemonSet has its own dedicated ServiceAccount with minimal RBAC permissions (node status patching for NPD conditions).

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
