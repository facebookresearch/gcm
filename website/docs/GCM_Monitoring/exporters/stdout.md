---
sidebar_position: 5
---

# Stdout

The Stdout exporter writes monitoring data and health check results directly to the terminal's standard output in JSON formatted string. It provides immediate visibility into collected data without requiring any configuration or external infrastructure.

## Configuration

### Available Options

The Stdout exporter accepts no configuration options (`--sink-opt` is not required).

### Basic Usage

The Stdout exporter requires no configuration:

```shell
# Monitoring with stdout
gcm slurm_monitor --sink=stdout --once

# Health checks with stdout
health_checks check-nvidia-smi fair_cluster prolog --sink=stdout
```

### Configuration File

Even in configuration files, no options are needed:

```toml
[gcm.slurm_monitor]
...
sink = "stdout"
```

## Use Cases

### Quick Inspection

Quickly inspect monitoring output during development:

```shell
# Check what data is being collected
gcm slurm_monitor --sink=stdout --once

# Verify health check output
health_checks check-dcgmi diag fair_cluster prolog --sink=stdout
```

### Pipeline Integration

Pipe output to other tools for processing:

```shell
# Pretty print with jq
gcm slurm_monitor --sink=stdout --once | jq '.'

# Extract specific fields
gcm slurm_monitor --sink=stdout --once | jq '.[].job_id'

# Filter data
gcm slurm_monitor --sink=stdout --once | jq '.[] | select(.state == "RUNNING")'

# Count results
gcm slurm_monitor --sink=stdout --once | jq 'length'
```

### Command Validation

Verify command syntax and options before running in production:

```shell
# Test command with all options
gcm slurm_monitor \
  --sink=stdout \
  --once \
  --verbose

# Validate health check parameters
health_checks check-storage disk-usage fair_cluster prolog \
  -v /dev/root \
  --usage-critical-threshold=85 \
  --sink=stdout
```

### Shell Scripting

Integrate GCM into shell scripts for custom workflows:

```shell
#!/bin/bash
# Check if any GPU is overheated
GPU_DATA=$(gcm nvml_monitor --sink=stdout --once)
HOT_GPUS=$(echo "$GPU_DATA" | jq '[.[] | select(.temperature > 80)] | length')

if [ "$HOT_GPUS" -gt 0 ]; then
    echo "Warning: $HOT_GPUS GPU(s) running hot!"
    exit 1
fi
```

### Comparison Testing

Compare output before and after changes:

```shell
# Capture baseline
gcm slurm_monitor --sink=stdout --once > baseline.json

# Make changes to system or code

# Capture new output
gcm slurm_monitor --sink=stdout --once > current.json

# Compare
diff baseline.json current.json
```

### Integration with Monitoring Tools

```shell
# Send to logging service
gcm slurm_monitor --sink=stdout --once | \
  curl -X POST -H "Content-Type: application/json" \
  -d @- https://logs.example.com/ingest

# Feed to metrics processor
gcm nvml_monitor --sink=stdout --once | \
  python process_metrics.py
```

## Performance Considerations

### Buffering

Standard output may be buffered, affecting real-time visibility:

```shell
# Force unbuffered output
PYTHONUNBUFFERED=1 gcm slurm_monitor --sink=stdout
```
