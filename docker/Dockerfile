# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# Multi-stage Docker build for GCM (GPU Cluster Monitoring) Python components.
# Provides both the `gcm` monitoring collector and `health_checks` CLI tools,
# with DCGM and optional cudaMemTest support for GPU health checking.
#
# Build:
#   docker build -f docker/Dockerfile -t gcm:dcgm4 .
#
# Build with cudaMemTest (required for memtest check):
#   docker build -f docker/Dockerfile --build-arg BUILD_CUDAMEMTEST=1 -t gcm:dcgm4 .
#
# Build with DCGM 3 (for older GPU drivers):
#   docker build -f docker/Dockerfile --build-arg DCGM_VERSION=3.3.7-1 -t gcm:dcgm3 .
#
# NOTE: GPU health checks require privileged access to function correctly.
# The container must be run with:
#   --gpus=all --pid=host -v /dev:/dev -v /sys:/sys:ro -v /var/log:/var/log:ro
# See charts/gcm/README.md for Kubernetes deployment guidance.

# ---------------------------------------------------------------------------
# Build stage — Python packages
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy project source and install the package itself (no deps, already installed)
COPY pyproject.toml .
COPY gcm/ gcm/
RUN pip install --no-cache-dir --no-deps --prefix=/install .

# ---------------------------------------------------------------------------
# CUDA build stage — cudaMemTest binary (optional)
# ---------------------------------------------------------------------------
FROM nvidia/cuda:12.2.2-devel-ubuntu22.04 AS cuda-builder

ARG BUILD_CUDAMEMTEST=0

WORKDIR /build
COPY gcm/health_checks/cuda/cudaMemTest.c .

# Only compile if BUILD_CUDAMEMTEST=1, otherwise create a placeholder
RUN if [ "$BUILD_CUDAMEMTEST" = "1" ]; then \
        nvcc -Xcompiler -O3 -Xcompiler -Wall -Xcompiler -fPIC -Xcompiler -Wextra \
            cudaMemTest.c -o cudaMemTest; \
    else \
        echo "cudaMemTest not built (set BUILD_CUDAMEMTEST=1 to enable)" > /build/cudaMemTest.skip; \
    fi

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.10-slim

LABEL org.opencontainers.image.source=https://github.com/facebookresearch/gcm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/slurm/bin:${PATH}"

# Install DCGM client libraries (required for check-dcgmi checks)
# NOTE: Using [trusted=yes] because NVIDIA's repo GPG key uses SHA1,
# which Debian rejects as of Feb 2026. Revert to signed-by once NVIDIA
# updates their signing key.
# DCGM 3.x and 4.x packages are sourced from the ubuntu2204 repo;
# ubuntu2004 is only used for DCGM < 3 (which is very old).
ARG DCGM_VERSION=4.4.2-1
RUN DCGM_MAJOR="${DCGM_VERSION%%.*}" && \
    if [ "$DCGM_MAJOR" -ge 4 ]; then \
        DCGM_PKG="datacenter-gpu-manager-${DCGM_MAJOR}-core"; \
        DCGM_REPO="ubuntu2204"; \
        DCGM_APT_VER="1:${DCGM_VERSION}"; \
    elif [ "$DCGM_MAJOR" -ge 3 ]; then \
        DCGM_PKG="datacenter-gpu-manager"; \
        DCGM_REPO="ubuntu2204"; \
        DCGM_APT_VER="1:${DCGM_VERSION%%-*}"; \
    else \
        DCGM_PKG="datacenter-gpu-manager"; \
        DCGM_REPO="ubuntu2004"; \
        DCGM_APT_VER="1:${DCGM_VERSION%%-*}"; \
    fi && \
    apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    echo "deb [trusted=yes] https://developer.download.nvidia.com/compute/cuda/repos/${DCGM_REPO}/x86_64/ /" \
        > /etc/apt/sources.list.d/cuda.list && \
    apt-get -o Acquire::Retries=5 update && \
    apt-get install -y --no-install-recommends "${DCGM_PKG}=${DCGM_APT_VER}" && \
    apt-get purge -y curl && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Install runtime utilities needed by health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        util-linux \
        procps \
        iproute2 \
        pciutils && \
    rm -rf /var/lib/apt/lists/*

# Create unversioned libnvidia-ml.so symlink for gni_lib (GPU Node ID).
# The NVIDIA container runtime injects libnvidia-ml.so.1 but not the
# unversioned .so, which cffi/dlopen-based libraries need.
RUN ln -sf /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 \
           /usr/lib/x86_64-linux-gnu/libnvidia-ml.so

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy cudaMemTest binary if it was built
ARG BUILD_CUDAMEMTEST=0
COPY --from=cuda-builder /build/cudaMemTest* /tmp/cuda-build/
RUN if [ "$BUILD_CUDAMEMTEST" = "1" ] && [ -f /tmp/cuda-build/cudaMemTest ]; then \
        cp /tmp/cuda-build/cudaMemTest /usr/local/bin/cudaMemTest && \
        chmod +x /usr/local/bin/cudaMemTest; \
    fi && \
    rm -rf /tmp/cuda-build

# Create log directory for health check output
RUN mkdir -p /var/log/gcm

WORKDIR /opt/gcm

# Verify entry points are available
RUN gcm --help > /dev/null 2>&1 && health_checks --help > /dev/null 2>&1

HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD ["python", "-c", "import gcm"]

ENTRYPOINT ["gcm"]
CMD ["--help"]
