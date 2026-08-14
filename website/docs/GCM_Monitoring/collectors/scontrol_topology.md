# scontrol_topology

## Overview

Collects Slurm topology from `scontrol show topo` every 60 seconds. Run one
instance per cluster, on the same controller-side host as `scontrol.service`.

The collector supports block topology (`BlockName`, `BlockIndex`, and
`BlockSize`) and switch topology (`SwitchName`, `Level`, `LinkSpeed`, and
`Switches`). Slurm hostlists are expanded into the `Nodes` tag set, and
`node_count` records the full number of nodes before the 10,000-entry safety
limit is applied.

**Data Type**: `DataType.LOG`, **Schema**: `ScontrolTopology`

## Execution Scope

Single node in the cluster. The host must have permission to run
`scontrol show topo`.

## Output Schema

The collector publishes one record per block or switch returned by Slurm.
Fields that do not apply to the cluster's topology plugin are omitted.

```python
{
    "cluster": str,                # Cluster identifier
    "derived_cluster": str | None, # Derived identifier for heterogeneous clusters

    # Block topology
    "BlockName": str | None,
    "BlockIndex": int | None,
    "BlockSize": int | None,

    # Switch topology
    "SwitchName": str | None,
    "Level": int | None,
    "LinkSpeed": int | None,
    "Switches": str | None,        # Child switch expression

    "Nodes": list[str] | None,     # Expanded Slurm hostlist
    "node_count": int,             # Number of nodes before truncation
}
```

Node lists longer than 10,000 entries are truncated to protect the collector;
`node_count` still contains the untruncated count.

## Packaged Service

The packaged `scontrol_topology.service` runs the collector with the settings
from the `[gcm.scontrol_topology]` section of `/etc/fb-gcm/config.toml`. The
packaged configuration uses the OpenTelemetry exporter; configure its endpoint
and resource attributes for your observability backend before enabling the
service.

```bash
systemctl enable --now scontrol_topology.service
systemctl status scontrol_topology.service
```

Only enable the service on one monitoring host per cluster to avoid duplicate
rows.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cluster` | String | Auto-detected | Cluster identifier |
| `--sink` | String | `stdout` | Sink destination; see [Exporters](../exporters/README.md) |
| `--sink-opt` | Multiple | - | Sink-specific option in OmegaConf dot-list syntax |
| `--log-level` | Choice | `INFO` | Logging verbosity |
| `--log-folder` | Path | `sacct_running_logs` | Parent directory for collector logs |
| `--stdout` | Flag | False | Write collector logs to standard output |
| `--heterogeneous-cluster-v1` | Flag | False | Compute a derived cluster identifier |
| `--interval` | Integer | 60 | Seconds between collection cycles |
| `--once` | Flag | False | Collect once and exit |
| `--retries` | Integer | 2 | Maximum sink write retries |
| `--dry-run` | Flag | False | Publish records to standard output |
| `--chunk-size` | Integer | `1M` | Maximum sink write chunk size in bytes |

Values in `/etc/fb-gcm/config.toml` override these command-line defaults for
the packaged service.

## Usage Examples

### One-Time Collection

Inspect a snapshot without sending it to a remote backend:

```bash
gcm scontrol_topology --once --sink stdout
```

### OpenTelemetry Export

Publish through an OTLP-compatible backend:

```bash
gcm scontrol_topology --once \
  --sink otel \
  --sink-opt otel_endpoint=http://localhost:4318 \
  --sink-opt "log_resource_attributes={'service.name': 'gcm'}"
```

### Custom Collection Interval

Collect every five minutes and publish to a file:

```bash
gcm scontrol_topology \
  --interval 300 \
  --sink file \
  --sink-opt filepath=/tmp/slurm-topology.jsonl
```
