<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Docker

Docker images for GCM (GPU Cluster Monitoring) components.

## GCM Python Image

The `Dockerfile.gcm` image packages both the `gcm` monitoring collector and the `health_checks` CLI into a single container.

### Build

```shell
docker build -f docker/Dockerfile.gcm -t gcm:latest .
```

### Multi-platform Build

```shell
docker buildx create --use
docker buildx build -f docker/Dockerfile.gcm \
  --platform linux/amd64,linux/arm64 \
  -t gcm:latest .
```

### Usage

Run the monitoring collector:

```shell
docker run --rm gcm:latest gcm --sink=stdout --once --cluster=my-cluster
```

Run health checks:

```shell
docker run --rm gcm:latest health_checks --help
```

### Security

The image follows container security best practices:

- Runs as non-root user (UID 65532)
- No shell login for the runtime user
- `HEALTHCHECK` instruction for orchestrator integration
- Minimal base image (`python:3.10-slim`)
- Build dependencies are excluded from the runtime image

## Slurmprocessor

The slurmprocessor is an OpenTelemetry Collector processor (Go library), not a standalone binary. It must be compiled into a [custom OpenTelemetry Collector](https://opentelemetry.io/docs/collector/custom-collector/). See [slurmprocessor/README.md](../slurmprocessor/README.md) for build instructions.
