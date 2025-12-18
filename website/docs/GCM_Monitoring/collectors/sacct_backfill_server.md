# sacct_backfill_server

## Overview
Coordination server that synchronizes multiple `sacct_backfill` processes across different clusters to ensure they process data in lockstep. Required when writing to Hive partitions that cannot be updated once written. Provides barrier synchronization to coordinate the backfill processes.

**Data Type**: N/A (coordination server, not a collector)
**Schemas**: N/A

## Execution Scope

Single coordination node (accessible to all cluster coordinator nodes).

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-p`, `--port` | Integer | 50000 | Port to listen on for client connections |
| `--nprocs` | Integer | **Required** | Number of client processes to synchronize |

## Usage Examples

### Basic Server Setup
```bash
# Start server expecting 3 clients
gcm sacct_backfill_server --nprocs 3 --port 50000

# Output:
# Server address: ('0.0.0.0', 50000)
# Authentication key: abc123def456...
```

### Multi-Cluster Coordination
```bash
# On coordination server
gcm sacct_backfill_server --nprocs 3 --port 50000
# Output: Authentication key: 1a2b3c4d...

# On cluster1
gcm sacct_backfill --once new \
  --rendezvous-host coord.example.com \
  --rendezvous-port 50000 \
  --authkey 1a2b3c4d... \
  --start "7 days ago" --end "now" \
  -- \
  gcm sacct_publish --sink graph_api

# On cluster2
gcm sacct_backfill --once new \
  --rendezvous-host coord.example.com \
  --rendezvous-port 50000 \
  --authkey 1a2b3c4d... \
  --start "7 days ago" --end "now" \
  -- \
  gcm sacct_publish --sink graph_api

# On cluster3
gcm sacct_backfill --once new \
  --rendezvous-host coord.example.com \
  --rendezvous-port 50000 \
  --authkey 1a2b3c4d... \
  --start "7 days ago" --end "now" \
  -- \
  gcm sacct_publish --sink graph_api

# All three will wait at each time chunk until all have completed
```
