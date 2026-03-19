---
sidebar_position: 6
---

# Slurm REST API Client

The `SlurmRestClient` provides the same `SlurmClient` interface as the CLI-based `SlurmCliClient`, but queries the Slurm REST API (`slurmrestd`) over HTTP instead of executing subprocess commands. This is useful for environments where Slurm CLI tools are not installed on monitoring hosts.

## Configuration

### Constructor Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `base_url` | Yes | — | Base URL of the slurmrestd endpoint (e.g. `http://slurmctl:6820`) |
| `token` | No | `None` | JWT or API token for authentication |
| `api_version` | No | `v0.0.40` | Slurm REST API version string |
| `session` | No | `None` | Custom `requests.Session` for connection pooling or testing |
| `timeout` | No | `30` | HTTP request timeout in seconds |
| `verify_ssl` | No | `True` | Enable/disable SSL certificate verification |

### Authentication

The client authenticates via the `X-SLURM-USER-TOKEN` header. Pass a JWT token to the `token` parameter:

```python
from gcm.monitoring.slurm.rest_client import SlurmRestClient

client = SlurmRestClient(
    base_url="https://slurmctl.cluster.example.com:6820",
    token="your-jwt-token-here",
)
```

## Supported Operations

The REST client supports all `SlurmClient` Protocol methods except where noted:

| Method | REST Endpoint | Notes |
|--------|--------------|-------|
| `squeue()` | `GET /slurm/{version}/jobs` | Maps REST field names to CLI field names |
| `sinfo()` | `GET /slurm/{version}/nodes` | Returns pipe-delimited lines |
| `sdiag_structured()` | `GET /slurm/{version}/diag` | Returns `Sdiag` dataclass directly |
| `sinfo_structured()` | `GET /slurm/{version}/nodes` | Returns `Sinfo` dataclass directly |
| `sacctmgr_qos()` | `GET /slurmdb/{version}/qos` | Returns pipe-delimited lines |
| `sacctmgr_user()` | `GET /slurmdb/{version}/users` | Returns usernames |
| `sacctmgr_user_info()` | `GET /slurmdb/{version}/users/{name}` | Returns pipe-delimited user details |
| `sacct_running()` | `GET /slurmdb/{version}/jobs?state=running` | Returns delimiter-separated lines |
| `scontrol_partition()` | `GET /slurm/{version}/partitions` | Returns key=value lines |
| `sshare()` | `GET /slurm/{version}/shares` | Returns pipe-delimited fair-share data |
| `sshare_structured()` | `GET /slurm/{version}/shares` | Returns `SshareRow` instances |
| `scontrol_config()` | — | **Not available** via REST API (`/slurmdb/config` is slurmdbd, not slurmctld) |
| `sprio()` | — | **Not available** via REST API |
| `count_runaway_jobs()` | — | **Not available** via REST API |

## Usage Examples

### Basic Usage

```python
from gcm.monitoring.slurm.rest_client import SlurmRestClient

client = SlurmRestClient(
    base_url="http://slurmctl:6820",
    token="your-jwt-token",
)

# Get node information as pipe-delimited lines
for line in client.sinfo():
    print(line)

# Get scheduler diagnostics
diag = client.sdiag_structured()
print(f"Thread count: {diag.server_thread_count}")
print(f"Jobs running: {diag.sdiag_jobs_running}")

# Get structured node information
sinfo = client.sinfo_structured()
for node in sinfo.nodes:
    print(f"{node.name}: {node.state} ({node.alloc_cpus}/{node.total_cpus} CPUs)")

# Get fair-share data
for line in client.sshare():
    print(line)
```

### Custom Session with Connection Pooling

```python
import requests
from gcm.monitoring.slurm.rest_client import SlurmRestClient

session = requests.Session()
session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=10))

client = SlurmRestClient(
    base_url="https://slurmctl:6820",
    token="your-jwt-token",
    session=session,
    timeout=60,
)
```

### Using with Existing GCM Collectors

The `SlurmRestClient` implements the same `SlurmClient` Protocol, so it can be used as a drop-in replacement wherever `SlurmCliClient` is used:

```python
from gcm.monitoring.slurm.rest_client import SlurmRestClient

# Create REST-based client instead of CLI-based
client = SlurmRestClient(
    base_url="http://slurmctl:6820",
    token="your-jwt-token",
)

# Pass to any function that accepts SlurmClient
# e.g., collectors, monitors, etc.
```

## Limitations

- **`sprio()`**: The Slurm REST API does not expose a priority factors endpoint. Use `SlurmCliClient` for priority data.
- **`scontrol_config()`**: The `/slurmdb/config` endpoint returns slurmdbd configuration, not slurmctld configuration. Use `SlurmCliClient` for controller config.
- **`count_runaway_jobs()`**: Requires `sacctmgr show runaway` which is not available via the REST API. Use `SlurmCliClient` for runaway job detection.
- **Field mapping**: The `squeue()` method maps REST API field names to CLI field names. Some version-dependent fields may require updates to the mapping table.
- **API version compatibility**: Tested with Slurm REST API v0.0.40+. Earlier versions may have different response schemas.

## Error Handling

The client raises `RuntimeError` on non-200 HTTP responses. Methods that are not supported raise `NotImplementedError` with a message indicating that the CLI client should be used instead.
