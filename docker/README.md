<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Docker

Docker images for GCM (GPU Cluster Monitoring) components.

## GCM Python Image

The `Dockerfile` image packages both the `gcm` monitoring collector and the `health_checks` CLI into a single container.

### Build

Standard build (includes DCGM):

```shell
docker build -f docker/Dockerfile -t gcm:latest .
```

With cudaMemTest (full GPU health check support):

```shell
docker build -f docker/Dockerfile \
  --build-arg BUILD_CUDAMEMTEST=1 \
  -t gcm:latest .
```

Override DCGM version:

```shell
docker build -f docker/Dockerfile \
  --build-arg DCGM_VERSION=3.3.5-1 \
  -t gcm:latest .
```

### Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `DCGM_VERSION` | `4.4.2-1` | DCGM client version to install |
| `BUILD_CUDAMEMTEST` | `0` | Set to `1` to compile and include `cudaMemTest` binary |

### Usage

Run the monitoring collector:

```shell
docker run --rm \
  --gpus=all \
  --pid=host \
  -u 0 \
  gcm:latest nvml_monitor --sink=stdout --cluster=my-cluster --interval=60
```

The monitoring collector requires `--gpus=all` for NVML GPU access, `--pid=host` and root (`-u 0`) to read `/proc/<pid>/environ` for Slurm job association. Add `--once` to collect a single sample and exit.

Run a single health check:

```shell
docker run --rm \
  --gpus=all \
  --pid=host \
  --privileged \
  -v /dev:/dev \
  -v /sys:/sys:ro \
  -v /var/log:/var/log:ro \
  --entrypoint health_checks \
  gcm:latest check-nvidia-smi -c gpu_num --sink stdout my-cluster app
```

For continuous health checks without Kubernetes, use the NPD-GCM image which runs all 6 checks on a schedule. See the [Helm chart README](deploy/helm/gcm/README.md) for the full list of checks, or run standalone with Docker Compose / systemd.

### Privileged Access for GPU Health Checks

GPU health checks require host-level access to function correctly. The following flags are needed:

| Flag | Required By |
|------|-------------|
| `--gpus=all` | All GPU checks (`check-nvidia-smi`, `check-dcgmi`, `memtest`) |
| `--pid=host` | `check-process check-zombie` (host process visibility) |
| `-v /dev:/dev` | GPU device access |
| `-v /sys:/sys:ro` | PCI device enumeration (`check-pci`), sensor readings (`check-sensors`) |
| `-v /var/log:/var/log:ro` | Syslog analysis (`check-syslogs xid`, `check-syslogs link-flaps`) |
| `--privileged` | DCGM diagnostics (`check-dcgmi diag`), IPMI access (`check-ipmitool`) |

The monitoring collector (`gcm`) does **not** require privileged access — only health checks do.

### NVML Symlink

The image creates an unversioned `libnvidia-ml.so` symlink pointing to `libnvidia-ml.so.1`. The NVIDIA container runtime injects the versioned `.so.1` at runtime but not the unversioned `.so`, which `cffi`/`dlopen`-based libraries (e.g., `gni_lib` for GPU Node ID) require.

## NPD-GCM Image

The `Dockerfile.npd` combines [Node Problem Detector](https://github.com/kubernetes/node-problem-detector) with the GCM image. NPD runs as the entrypoint and invokes GCM health check binaries as custom plugin monitors.

### Build

Build the base GCM image first, then the NPD-GCM image:

```shell
docker build -f docker/Dockerfile -t gcm:latest .
docker build -f docker/Dockerfile.npd -t gcm-npd:latest .
```

## Slurmprocessor

The slurmprocessor is an OpenTelemetry Collector processor (Go library), not a standalone binary. It must be compiled into a [custom OpenTelemetry Collector](https://opentelemetry.io/docs/collector/custom-collector/). See [slurmprocessor/README.md](../slurmprocessor/README.md) for build instructions.
