---
sidebar_position: 7
---

# Telemetry

The Telemetry exporter appends structured telemetry snapshots to a local file in JSON or CSV format for offline analysis.

## Configuration

| Option | Required | Description |
|--------|----------|-------------|
| `file_path` | Yes | Path to the output file |
| `format` | No | `json` (default) or `csv` |

## Usage

```shell
# JSON (NDJSON, one object per line)
gcm nvml_monitor --sink=telemetry --sink-opt file_path=/var/log/gcm/telemetry.json --once

# CSV
gcm nvml_monitor --sink=telemetry --sink-opt file_path=/var/log/gcm/telemetry.csv --sink-opt format=csv --once
```

## Output

Each snapshot adds a timestamp and writes one record per GPU. Example JSON:

```json
{"timestamp": "2026-03-04T21:31:22", "hostname": "node-42", "gpu_id": 3, "job_id": 91283, "job_user": "research_team", "gpu_util": 88, "mem_used_percent": 71, "temperature": 78, "power_draw": 310, "retired_pages_count_single_bit": 0, "retired_pages_count_double_bit": 0}
```
