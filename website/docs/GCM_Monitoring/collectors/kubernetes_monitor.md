# kubernetes_monitor

## Overview
Collects Kubernetes pod and node condition metrics for SUNK (Slurm-on-Kubernetes) cluster monitoring. Provides visibility into pod lifecycle states, container restart counts, node health conditions, and Slurm-K8s job correlation via annotations.

**Data Type**: `DataType.METRIC`, **Schemas**: `KubernetesPodPayload`, `KubernetesNodePayload`

## Execution Scope

Single node in the cluster with access to the Kubernetes API (typically a management node or pod with ServiceAccount).

## Prerequisites

Install the optional Kubernetes dependency:

```bash
pip install 'gpucm[kubernetes]'
```

## Output Schema

### KubernetesPodPayload
Published with `DataType.METRIC` and `DataIdentifier.K8S_POD`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "collection_unixtime": int,   # Unix timestamp of collection
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (optional)
    "pod": {
        "name": str,              # Pod name
        "namespace": str,         # Kubernetes namespace
        "node_name": str,         # Node the pod is scheduled on
        "phase": str,             # Pod phase (Pending/Running/Succeeded/Failed/Unknown)
        "restart_count": int,     # Container restart count
        "container_name": str,    # Container name (one row per container)
        "slurm_job_id": str,      # Slurm job ID from annotation slurm.coreweave.com/job-id
    }
}
```

### KubernetesNodePayload
Published with `DataType.METRIC` and `DataIdentifier.K8S_NODE`:

```python
{
    "ds": str,                    # Collection date (YYYY-MM-DD in Pacific time)
    "collection_unixtime": int,   # Unix timestamp of collection
    "cluster": str,               # Cluster identifier
    "derived_cluster": str,       # Sub-cluster (optional)
    "node_condition": {
        "name": str,              # Node name
        "condition_type": str,    # Condition type (Ready, MemoryPressure, DiskPressure, etc.)
        "status": str,            # Condition status (True/False/Unknown)
        "reason": str,            # Machine-readable reason
        "message": str,           # Human-readable message
    }
}
```

**Important Notes:**
1. Each container in a pod creates a separate record (one row per container)
2. Pods without containers (e.g., Pending) still produce one record with `restart_count=0`
3. The `slurm_job_id` field correlates Kubernetes pods with Slurm jobs in SUNK environments

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cluster` | String | Auto-detected | Cluster name for metadata enrichment |
| `--sink` | String | **Required** | Sink destination, see [Exporters](../exporters/README.md) |
| `--sink-opts` | Multiple | - | Sink-specific options |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--stdout` | Flag | False | Display metrics to stdout in addition to logs |
| `--interval` | Integer | 60 | Seconds between collection cycles (1 minute) |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | Maximum size in bytes of each chunk when writing data to sink |
| `--namespace` | String | "" (all) | Kubernetes namespace to filter pods |
| `--in-cluster/--no-in-cluster` | Flag | True | Use in-cluster ServiceAccount or local kubeconfig |
| `--label-selector` | String | "" | Kubernetes label selector to filter pods (e.g., `app=slurm`) |

## Usage Examples

### Basic Continuous Collection (In-Cluster)
```bash
gcm kubernetes_monitor --sink otel
```

### One-Time Snapshot
```bash
gcm kubernetes_monitor --once --sink stdout --dry-run
```

### Filter by Namespace with Label Selector
```bash
gcm kubernetes_monitor \
  --sink otel \
  --namespace slurm-jobs \
  --label-selector "app=slurm-worker"
```

### Using Kubeconfig (Out-of-Cluster)
```bash
gcm kubernetes_monitor \
  --no-in-cluster \
  --once \
  --sink stdout \
  --cluster my-sunk-cluster
```

### Debug Mode
```bash
gcm kubernetes_monitor \
  --once \
  --log-level DEBUG \
  --stdout \
  --dry-run \
  --no-in-cluster
```
