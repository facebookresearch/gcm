---
sidebar_position: 2
---

# Kubernetes Deployment

GCM Monitoring can be deployed on Kubernetes GPU clusters as a DaemonSet that runs `gcm nvml_monitor` on every GPU node.

## Architecture

```
DaemonSet (one per GPU node)
  └── Pod
       └── Container: gcm nvml_monitor
            └── Runs: gcm nvml_monitor --sink otel --cluster my-cluster --interval 60
```

The monitoring DaemonSet continuously collects per-device GPU metrics via NVML:

- **Per-GPU**: utilization, memory usage, temperature, power draw, ECC retired pages
- **Per-GPU job association**: Slurm job ID, user, partition, and resource allocation
- **Host-level**: min/max/avg GPU utilization, RAM utilization

Job association works by reading `/proc/<pid>/environ` of GPU compute processes to extract Slurm environment variables (`SLURM_JOB_ID`, `SLURM_JOB_USER`, etc.).

## Helm Chart

The recommended way to deploy on Kubernetes is via the [GCM Helm chart](https://github.com/facebookresearch/gcm/tree/main/charts/gcm):

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

Or from source:

```shell
helm install gcm charts/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster
```

See the [Helm chart README](https://github.com/facebookresearch/gcm/tree/main/charts/gcm/README.md) for full configuration options.

### Configuration

| Parameter | Description | Default |
|---|---|---|
| `monitoring.sink` | Exporter sink for metrics (e.g., `otel`, `stdout`) | `""` |
| `monitoring.cluster` | Cluster name for metrics | `""` |
| `monitoring.interval` | Collection interval in seconds | `60` |
| `monitoring.sinkOpts` | Sink options (`-o`, OmegaConf dot-list syntax) | `[]` |
| `monitoring.extraArgs` | Additional CLI arguments for `gcm nvml_monitor` | `[]` |
| `monitoring.extraEnv` | Additional environment variables | `[]` |

### Sending Metrics to OpenTelemetry

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set monitoring.extraEnv[0].name=OTEL_EXPORTER_OTLP_ENDPOINT \
  --set monitoring.extraEnv[0].value=http://otel-collector:4318
```

Sink-specific options can also be passed via `monitoring.sinkOpts`:

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  --set monitoring.sink=otel \
  --set monitoring.cluster=my-cluster \
  --set monitoring.sinkOpts[0]=otel_endpoint=http://otel-collector:4318 \
  --set "monitoring.sinkOpts[1]=metric_resource_attributes={'environment': 'production'}"
```

Run `gcm nvml_monitor --help` to see all available sinks and their options.

## Docker Image

The monitoring DaemonSet uses the base GCM Docker image:

```shell
docker build -f docker/Dockerfile -t gcm:latest .
```

## Security Requirements

The monitoring DaemonSet requires:

- **`runAsUser: 0`** (root): needed to read `/proc/<pid>/environ` of GPU compute processes for Slurm job association
- **`hostPID: true`**: NVML reports GPU process PIDs in the host PID namespace, so the container needs host PID namespace visibility
- **`NVIDIA_VISIBLE_DEVICES=all`**: GPU access without reserving any GPU resources
- **`priorityClassName: system-node-critical`**: prevents eviction under resource pressure

The monitoring DaemonSet does **not** require `privileged` mode or `hostNetwork`.

## Non-Kubernetes Deployment

For bare-metal or non-Kubernetes environments, `gcm nvml_monitor` can be run directly as a systemd service. See the [Getting Started](./getting_started.md) guide for CLI usage.
