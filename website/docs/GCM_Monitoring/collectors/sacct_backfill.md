# sacct_backfill

## Overview
Orchestrates historical SLURM job data collection by partitioning large time ranges into manageable chunks and systematically backfilling them through `sacct_wrapper` and `sacct_publish`. Supports parallel processing, retry of failed chunks, and rendezvous synchronization for multi-cluster coordination when writing to immutable storage.

**Data Type**: N/A (orchestrator that invokes other collectors)
**Schemas**: N/A (orchestrator)

## Execution Scope

Single node in the cluster.

## Command-Line Options


| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--cluster` | String | Auto-detected | Cluster name for metadata enrichment |
| `--sacct-timeout` | Integer | 120 | Timeout in seconds for each `sacct` call |
| `--publish-timeout` | Integer | 120 | Timeout in seconds for each `sacct_publish` call |
| `--concurrently` | Integer | 1 | Maximum number of publishes that can occur concurrently (0 = unlimited). |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--stdout` | Flag | False | Display metrics to stdout in addition to logs |
| `--heterogeneous-cluster-v1` | Flag | False | Enable per-partition metrics for heterogeneous clusters |
| `--interval` | Integer | 300 | Seconds between collection cycles (5 minutes) |
| `--once` | Flag | False | Run once and exit (no continuous monitoring) |
| `--retries` | Integer | Shared default | Retry attempts on sink failures |
| `--dry-run` | Flag | False | Print to stdout instead of publishing to sink |
| `--chunk-size` | Integer | Shared default | The maximum size in bytes of each chunk when writing data to sink.  |
| `--sleep` | Integer | 10 | Seconds to wait between chunks (serial mode only) |
| `--rendezvous-host` | IP Address | None | Host running rendezvous server. Synchronize backfill processes across multiple clusters (see [sacct_backfill_server](sacct_backfill_server.md)) |
| `--rendezvous-port` | Integer | 50000 | Port of rendezvous server |
| `--authkey` | UUID | **Required with host** | Authentication key from server |
| `--rendezvous-timeout` | Integer | 60 | Seconds to wait for synchronization |

## Subcommands

### `new` - Start New Backfill
Partition a time range and backfill all chunks.

#### Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-s`, `--start` | String | `3 hours ago` | Start time (parsed by GNU `date -d`) |
| `-e`, `--end` | String | `now` | End time (parsed by GNU `date -d`) |
| `--step` | Integer | 1 | Chunk size in hours |
| `PUBLISH_CMD` | Arguments | **Required** | Command to publish each chunk (after `--`). See [sacct_publish](sacct_publish.md) |

### `from_file` - Retry Failed Chunks
Backfill specific time intervals from a CSV file. Used to retry chunks that failed in previous runs.

#### Options
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--intervals` | File | stdin | CSV file with (start, end) pairs |
| `PUBLISH_CMD` | Arguments | **Required** | Command to publish each chunk (after `--`). See [sacct_publish](sacct_publish.md) |

## Usage Examples

### Basic Backfill
```bash
# Last 24 hours, one chunk at a time
gcm sacct_backfill --once new \
  -s "1 day ago" \
  -e "now" \
  -- \
  gcm sacct_publish --sink stdout
```

### Large Historical Backfill
```bash
# 1 year of data in 2-hour chunks, 5 concurrent
gcm sacct_backfill --once new \
  -s "jan 1 2023" \
  -e "dec 31 2023" \
  --step 2 \
  --concurrently 5 \
  -- \
  gcm sacct_publish \
    --sink otel \
    -o "log_resource_attributes={'key': 'val'}" \
  2> backfill_errors.log
```

### Continuous Backfill
```bash
# Run every hour, backfill last 3 hours
gcm sacct_backfill new \
  -s "3 hours ago" \
  -e "now" \
  --interval 3600 \
  -- \
  gcm sacct_publish --sink otel
```

### Multi-Cluster Synchronized Backfill
```bash
# Start server (on coordinator node)
gcm sacct_backfill_server --nprocs 3
# Note the authkey output

# On cluster1
gcm sacct_backfill --once new \
  --rendezvous-host coordinator.example.com \
  --rendezvous-port 50000 \
  --authkey <UUID> \
  --cluster cluster1 \
  -s "7 days ago" -e "now" \
  -- \
  gcm sacct_publish --sink graph_api

# On cluster2 and cluster3 (same command with different clusters)
# All three will process chunks in lockstep
```
