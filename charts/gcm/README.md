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
- [DCGM](https://developer.nvidia.com/dcgm) running on GPU nodes (required for `check-dcgmi` health checks; typically deployed via the [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html))
- GCM Docker image (see [docker/README.md](../../docker/README.md))
- NPD-GCM Docker image for health checks (see [docker/README.md](../../docker/README.md))

## Install

The chart is published to GHCR as an OCI artifact and versioned alongside GCM releases.

**DCGM 4** (default, requires NVIDIA driver R550+):

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set healthChecks.cluster=my-cluster \
  --set healthChecks.sink=otel \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

**DCGM 3** (for older NVIDIA drivers R535/R525):

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.image.tag=dcgm3 \
  --set healthChecks.image.tag=dcgm3 \
  --set healthChecks.cluster=my-cluster \
  --set healthChecks.sink=otel \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

To pin a specific chart version, add `--version X.Y.Z`.

Health checks and monitoring are independent — you can deploy either or both:

```shell
# Health checks only
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.enabled=false \
  --set healthChecks.cluster=my-cluster

# Monitoring only
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set healthChecks.enabled=false \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

## Health Checks DaemonSet (NPD-GCM)

Runs [Node Problem Detector](https://github.com/kubernetes/node-problem-detector) with GCM health checks as custom plugin monitors on every GPU node. NPD and GCM health checks run together in a single pod:

```
DaemonSet (one per node, controlled by nodeSelector/tolerations)
  └── Pod
       └── Container: node-problem-detector
            ├── Invokes: health_checks check-syslogs xid ...
            ├── Invokes: health_checks check-nvidia-smi ...
            ├── Invokes: health_checks check-dcgmi ...
            └── ...
```

NPD is the scheduler — it runs each GCM health check as a subprocess at a configurable interval, manages retries and concurrency, and reports results as Kubernetes node conditions and Prometheus metrics. GCM `health_checks` does the actual GPU inspection.

### Default Checks

The DaemonSet runs 6 health checks every 5 minutes (interval, timeout, and concurrency are configurable via `healthChecks.*` values):

| Check | Description | NPD Condition |
|-------|-------------|---------------|
| XID Errors | Scans syslogs for NVIDIA XID errors | `GcmXidErrorsProblem` |
| ECC Errors | Checks uncorrected/corrected ECC counters | `GcmSmiEccProblem` |
| GPU Disconnected | Verifies expected GPU count is visible | `GcmSmiDisconnectedProblem` |
| Zombie Processes | Detects zombie GPU processes | `GcmProcZombieProblem` |
| DCGM NVLink Status | Checks NVLink health via DCGM | `GcmDcgmiNvlinkStatusProblem` |
| DCGM Diag Level 1 | Runs DCGM level 1 diagnostics | `GcmDcgmiDiagProblem` |

### Adding Extra Checks

Additional checks can be added via `healthChecks.extraChecks` without modifying the chart. Each entry adds a new NPD condition and check rule. Run `health_checks --help` to see all available checks.

```yaml
# values.yaml
healthChecks:
  extraChecks:
    - condition: GcmPciProblem
      message: "PCI device check passed"
      args: ["check-pci"]
    - condition: GcmSensorsProblem
      message: "Sensor readings check passed"
      args: ["check-sensors"]
    - condition: GcmRowRemapProblem
      message: "GPU row remap check passed"
      args: ["check-nvidia-smi", "-c", "row_remap"]
```

### Querying Node Conditions

All GCM conditions are prefixed with `Gcm` for easy querying:

```shell
# List all GCM conditions on a node
kubectl get node <node-name> -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}' | grep Gcm
```

### Acting on Health Check Results

These conditions are standard Kubernetes node conditions. Downstream tools can watch them to automatically remediate unhealthy nodes:

- [Draino](https://github.com/planetlabs/draino), cluster autoscalers, or custom controllers can cordon, drain, or replace nodes based on conditions
- Health check results can be exported via the otel sink to your observability stack (e.g., [Grafana](https://grafana.com/)) for alerting and reporting to infrastructure providers

### Prometheus Metrics

NPD exposes Prometheus metrics on port 20257 (configurable via `healthChecks.prometheus.port`). The health checks DaemonSet includes a liveness probe on this port to detect stuck NPD processes.

### Building the NPD Image

The health checks DaemonSet uses a combined NPD+GCM image. Build it after building the base GCM image:

```shell
# Build the base GCM image first
docker build -f docker/Dockerfile -t gcm:latest .

# Build the NPD-GCM combined image
docker build -f docker/Dockerfile.npd -t gcm-npd:latest .
```

### Health Checks Configuration

| Parameter | Description | Default |
|---|---|---|
| `healthChecks.enabled` | Deploy the NPD health checks DaemonSet | `true` |
| `healthChecks.cluster` | Cluster name for health check results | `""` |
| `healthChecks.sink` | Sink for health check results | `"stdout"` |
| `healthChecks.sinkOpts` | Sink options (`--sink-opt`, OmegaConf dot-list syntax) | `[]` |
| `healthChecks.gpuCount` | Expected GPU count per node | `8` |
| `healthChecks.invokeInterval` | Check interval in seconds | `300` |
| `healthChecks.timeout` | NPD timeout per check in seconds (includes retries) | `480` |
| `healthChecks.maxRetries` | Max retries per check before reporting failure | `2` |
| `healthChecks.retrySleep` | Seconds to wait between retries | `30` |
| `healthChecks.concurrency` | Max concurrent checks | `3` |
| `healthChecks.extraChecks` | Additional health checks | `[]` |
| `healthChecks.extraEnv` | Additional environment variables | `[]` |

## Monitoring DaemonSet

Runs `gcm nvml_monitor` on every GPU node to collect per-device GPU metrics via NVML:

- **Per-GPU**: utilization, memory usage, temperature, power draw, ECC retired pages
- **Per-GPU job association**: Slurm job ID, user, partition, and resource allocation (read from `/proc/<pid>/environ` of GPU compute processes)
- **Host-level**: min/max/avg GPU utilization, RAM utilization

The DaemonSet runs as root with `hostPID: true` so it can read the environment of GPU processes to associate metrics with Slurm jobs. It uses `NVIDIA_VISIBLE_DEVICES=all` for GPU access without reserving any GPU resources.

### Monitoring Configuration

| Parameter | Description | Default |
|---|---|---|
| `monitoring.enabled` | Deploy the monitoring DaemonSet | `true` |
| `monitoring.sink` | Exporter sink for metrics | `""` |
| `monitoring.sinkOpts` | Sink options (`-o`, OmegaConf dot-list syntax) | `[]` |
| `monitoring.cluster` | Cluster name for metrics | `""` |
| `monitoring.interval` | Collection interval in seconds | `60` |
| `monitoring.extraArgs` | Additional CLI arguments | `[]` |
| `monitoring.extraEnv` | Additional environment variables | `[]` |

## Sinks

The `sink` parameter controls where metrics and health check results are sent. Run `gcm nvml_monitor --help` or `health_checks --help` to see all available sinks and their options.

Sink-specific options can be passed via `sinkOpts` (OmegaConf dot-list syntax). The otel sink also supports standard `OTEL_EXPORTER_*` environment variables via `extraEnv`:

```shell
# Monitoring: send GPU metrics to an OpenTelemetry collector
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set monitoring.sinkOpts[0]=otel_endpoint=http://otel-collector:4318 \
  --set "monitoring.sinkOpts[1]=metric_resource_attributes={'environment': 'production'}"

# Health checks: send results to an OpenTelemetry collector
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set healthChecks.sink=otel \
  --set healthChecks.cluster=my-cluster \
  --set healthChecks.sinkOpts[0]=otel_endpoint=http://otel-collector:4318 \
  --set "healthChecks.sinkOpts[1]=log_resource_attributes={'environment': 'production'}"
```

## Node Scheduling

By default, both DaemonSets tolerate `nvidia.com/gpu` taints and schedule on **all** nodes. This works for clusters where the NVIDIA device plugin taints GPU nodes.

For clusters that use **labels** instead of taints to identify GPU nodes, use `nodeSelector` to restrict scheduling:

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
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

- **Health Checks DaemonSet**: Runs as **privileged** with `hostPID` and `hostNetwork` enabled. GPU health checks need direct access to GPU devices, host PCI topology, syslog files, DCGM diagnostics, and host process visibility. The health checks DaemonSet has its own dedicated ServiceAccount with minimal RBAC permissions (node status patching for NPD conditions).
- **Monitoring DaemonSet**: Runs as root (UID 0) with `hostPID: true`. Root is needed to read `/proc/<pid>/environ` of GPU compute processes for Slurm job association. `hostPID` is needed because NVML reports GPU process PIDs in the host PID namespace. GPU metrics (utilization, temperature, etc.) are collected via NVML, which requires access to the NVIDIA device files.

Both DaemonSets use `priorityClassName: system-node-critical` to prevent eviction under resource pressure — GPU monitoring must stay running when nodes are stressed.

## Testing

Lint the chart:

```shell
helm lint charts/gcm
```

Render templates locally:

```shell
helm template my-release charts/gcm \
  --set monitoring.sink=stdout \
  --set monitoring.cluster=test \
  --set healthChecks.cluster=test
```

Run Helm tests after install:

```shell
helm test my-release
```
