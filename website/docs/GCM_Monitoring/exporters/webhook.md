---
sidebar_position: 6
---

# Webhook

The Webhook exporter sends monitoring data and health check results to any HTTP endpoint via POST requests in JSON format. It supports optional bearer token authentication and SSL verification control.

## Configuration

### Available Options

| Option | Required | Description |
|--------|----------|-------------|
| `url` | Yes | HTTP endpoint URL to POST data to |
| `timeout` | No | Request timeout in seconds (default: 30) |
| `bearer_token` | No | Bearer token for Authorization header |
| `verify_ssl` | No | Enable/disable SSL certificate verification (default: true) |

### Basic Usage

```shell
# Send monitoring data to a webhook endpoint
gcm slurm_monitor --sink=webhook --sink-opt url=http://localhost:8080/ingest --once

# With authentication
gcm slurm_monitor \
  --sink=webhook \
  --sink-opt url=https://api.example.com/metrics \
  --sink-opt bearer_token=my-secret-token \
  --once
```

### Configuration File

```toml
[gcm.slurm_monitor]
sink = "webhook"
sink_opts = [
  "url=https://api.example.com/metrics",
  "bearer_token=my-secret-token",
  "timeout=60",
  "verify_ssl=true",
]
```

## Data Format

The exporter sends data as JSON arrays:

- **Logs**: Each message is serialized with `None` values removed
- **Metrics**: Each message is serialized with nested dictionaries flattened

Both types include a `Content-Type: application/json` header.

## Use Cases

### Forward to Internal API

Send monitoring data to an internal aggregation service:

```shell
gcm slurm_monitor \
  --sink=webhook \
  --sink-opt url=https://internal-api.corp.example.com/v1/metrics \
  --sink-opt bearer_token="${API_TOKEN}" \
  --sink-opt timeout=10
```

### Health Check Notifications

Forward health check results to an alerting endpoint:

```shell
health_checks check-nvidia-smi gpu-temperature \
  fair_cluster prolog \
  --sink=webhook \
  --sink-opt url=https://alerts.example.com/health
```

### Development with Insecure Endpoints

Disable SSL verification for local development:

```shell
gcm slurm_monitor \
  --sink=webhook \
  --sink-opt url=https://localhost:8443/ingest \
  --sink-opt verify_ssl=false \
  --once
```

## Error Handling

The exporter raises `requests.exceptions.HTTPError` on non-2xx responses. The upstream retry mechanism in `run_data_collection_loop` handles transient failures automatically when `--retries` is configured.
