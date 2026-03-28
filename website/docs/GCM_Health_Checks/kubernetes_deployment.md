---
sidebar_position: 2
---

# Kubernetes Deployment

GCM Health Checks can be deployed on Kubernetes GPU clusters using [Node Problem Detector (NPD)](https://github.com/kubernetes/node-problem-detector) as a DaemonSet. NPD runs each GCM health check as a subprocess at a configurable interval and reports results as Kubernetes node conditions.

## Architecture

```
DaemonSet (one per GPU node)
  └── Pod
       └── Container: node-problem-detector (NPD)
            ├── Invokes: health_checks check-syslogs xid ...
            ├── Invokes: health_checks check-nvidia-smi ...
            ├── Invokes: health_checks check-dcgmi ...
            └── ...
```

NPD is the scheduler — it runs each health check, manages retries (configurable via `healthChecks.maxRetries` and `healthChecks.retrySleep`) and concurrency, and reports results as:
- **Kubernetes node conditions** (e.g., `GcmXidErrorsProblem`) that downstream tools can act on
- **Prometheus metrics** for dashboarding and alerting

GCM `health_checks` does the actual GPU inspection.

## Helm Chart

The recommended way to deploy on Kubernetes is via the [GCM Helm chart](https://github.com/facebookresearch/gcm/tree/main/charts/gcm):

```shell
helm install gcm oci://ghcr.io/facebookresearch/charts/gcm \
  -f <PATH/TO>/custom-values.yaml \
  --namespace <namespace> \
  --set monitoring.enabled=false \
  --set healthChecks.enabled=true
```

Or from source:

```shell
helm install gcm charts/gcm \
  -f <PATH/TO>/custom-values.yaml \
  --namespace <namespace> \
  --set monitoring.enabled=false \
  --set healthChecks.enabled=true
```

See the [Helm chart README](https://github.com/facebookresearch/gcm/tree/main/charts/gcm/README.md) for full configuration options.

### Default Health Checks

The Helm chart runs 6 health checks every 5 minutes by default:

| Check | Description | NPD Condition |
|-------|-------------|---------------|
| XID Errors | Scans syslogs for NVIDIA XID errors | `GcmXidErrorsProblem` |
| ECC Errors | Checks uncorrected/corrected ECC counters | `GcmSmiEccProblem` |
| GPU Disconnected | Verifies expected GPU count is visible | `GcmSmiDisconnectedProblem` |
| Zombie Processes | Detects zombie GPU processes | `GcmProcZombieProblem` |
| DCGM NVLink Status | Checks NVLink health via DCGM | `GcmDcgmiNvlinkStatusProblem` |
| DCGM Diag Level 1 | Runs DCGM level 1 diagnostics | `GcmDcgmiDiagProblem` |

### Adding Extra Checks

Additional checks can be enabled via `healthChecks.extraChecks` in your values file. Each entry adds a new NPD condition and check rule without modifying the chart:

```yaml
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

Run `health_checks --help` to see all available checks, or see the [health checks reference](./health_checks/README.md) for detailed documentation on each check and its arguments.

### Querying Node Conditions

All GCM conditions are prefixed with `Gcm`:

```shell
# List all GCM conditions on a node
kubectl get node <node-name> \
  -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}' \
  | grep Gcm
```

### Acting on Results

Health check conditions are standard Kubernetes node conditions. Downstream tools can watch them to automatically remediate unhealthy nodes:

- **[Draino](https://github.com/planetlabs/draino)**: watches node conditions and automatically cordons/drains unhealthy nodes
- **Cluster autoscalers**: can detect unhealthy nodes and replace them
- **Custom controllers**: can implement organization-specific remediation workflows
- **OTel sink**: export results to your observability stack (e.g., [Grafana](https://grafana.com/)) for alerting and reporting to infrastructure providers

## Docker Image

The health checks DaemonSet uses a combined NPD+GCM Docker image. Build it after building the base GCM image:

```shell
# Build the base GCM image first
docker build -f docker/Dockerfile -t gcm:latest .

# Build the NPD-GCM combined image
docker build -f docker/Dockerfile.npd -t gcm-npd:latest .
```

The NPD image bundles [Node Problem Detector v0.8.19](https://github.com/kubernetes/node-problem-detector) with all GCM health check binaries.

## Security Requirements

The health checks DaemonSet requires elevated privileges:

- **`privileged: true`**: direct access to GPU devices, host PCI topology, and DCGM diagnostics
- **`hostPID: true`**: visibility into host processes for zombie detection and GPU process inspection
- **`hostNetwork: true`**: connectivity to the host's DCGM daemon for diagnostics
- **`CAP_SYSLOG`**: access to kernel ring buffer for XID error detection via `dmesg`
- **Dedicated ServiceAccount**: minimal RBAC permissions (node status patching for NPD conditions)
- **`priorityClassName: system-node-critical`**: prevents eviction under resource pressure

## Non-Kubernetes Deployment

For bare-metal or non-Kubernetes environments, health checks can be run directly via the CLI or as systemd services. See the [Getting Started](./getting_started.md) guide for CLI usage.
