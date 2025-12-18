---
sidebar_position: 2
---

# File

The File exporter writes monitoring data and health check results to local file system storage in JSON format

## Configuration

### Available Options

| Option | Required | Description |
|--------|----------|-------------|
| `file_path` | Yes | Path to the output file |

### Basic Usage

At least one file path must be specified when using the File exporter:

```shell
# Single output file for all data
gcm slurm_monitor --sink=file --sink-opt file_path=/var/log/gcm/monitoring.json --once
```

### Configuration File

```toml
[gcm.slurm_monitor]
...
sink = "file"
sink_opts = [
  "file_path=/var/log/gcm/monitoring.json",
]
```

## Output Format

Data is written as newline-delimited JSON (NDJSON), with each monitoring event on a separate line:

```json
{"timestamp": "2024-10-30T01:45:52Z", "job_id": "12345", "state": "RUNNING", ...}
{"timestamp": "2024-10-30T01:46:52Z", "job_id": "12346", "state": "PENDING", ...}
```

This format allows for:
- Efficient appending of new data
- Line-by-line processing with standard tools
- Easy parsing with JSON libraries

## Use Cases

### Production Monitoring

Store monitoring data locally for analysis and debugging:

```shell
# Continuous monitoring to file
gcm slurm_monitor --sink=file --sink-opt file_path=/var/log/gcm/monitoring.json
```

### Integration with Log Processors

Write to files that are monitored by log aggregation tools:

```shell
# Write to directory monitored by Filebeat, Fluentd, etc.
gcm slurm_monitor --sink=file --sink-opt file_path=/var/log/gcm/slurm.json
```

### Debugging and Development

Capture output during development for inspection:

```shell
gcm slurm_monitor --sink=file --sink-opt file_path=/tmp/debug.json --once
cat /tmp/debug.json | jq '.'
```

## File Management

### Directory Creation

The exporter automatically creates parent directories if they don't exist:

```shell
# Creates /var/log/gcm/ if it doesn't exist
gcm slurm_monitor --sink=file --sink-opt file_path=/var/log/gcm/data.json --once
```

### Log Rotation

The File exporter uses Python's logging infrastructure with built-in log rotation support. This means you don't need external tools like `logrotate` for basic rotation needs. The rotation happens transparently as part of the logging system.

> The file exporter is not currently exposing the log rotation options. Feel free to [open a feature request](https://github.com/facebookresearch/gcm/issues) if you need this feature.

### Permissions

Ensure the process has write permissions to the target directory:

```shell
# Create directory with appropriate permissions
sudo mkdir -p /var/log/gcm
sudo chown $USER:$USER /var/log/gcm
```

## File Write Failures

Check permissions and disk space if writes fail:

```shell
# Check disk space
df -h /var/log/gcm

# Check permissions
ls -ld /var/log/gcm
```
