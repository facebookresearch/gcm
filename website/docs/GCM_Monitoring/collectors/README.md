# GCM Collectors Documentation

This directory contains documentation for all GCM monitoring collectors. Collectors are CLI tools that gather metrics and data from various sources (SLURM, GPUs, storage, etc.) and publish them to configured sinks.

## Collectors

- **[nvml_monitor](nvml_monitor.md)** - Collects GPU metrics using NVIDIA NVML library
- **[sacct_backfill](sacct_backfill.md)** - Backfills historical job data in time-chunked batches
- **[sacct_backfill_server](sacct_backfill_server.md)** - Coordination server for multi-cluster backfills
- **[sacct_publish](sacct_publish.md)** - Transforms and publishes sacct output to sinks
- **[sacct_running](sacct_running.md)** - Continuously monitors running jobs
- **[sacct_wrapper](sacct_wrapper.md)** - Wrapper for strict time-bounded sacct queries
- **[sacctmgr_qos](sacctmgr_qos.md)** - Collects Quality of Service configurations
- **[sacctmgr_user](sacctmgr_user.md)** - Collects user account information and associations
- **[scontrol](scontrol.md)** - Collects partition configuration
- **[scontrol_config](scontrol_config.md)** - Collects cluster-wide configuration
- **[slurm_job_monitor](slurm_job_monitor.md)** - Real-time node and job monitoring
- **[slurm_monitor](slurm_monitor.md)** - Comprehensive cluster-wide metrics aggregation
- **[sprio](sprio.md)** - Collects job priority factors for pending jobs

## Common Concepts

### Sinks/Exporters
Collectors support pluggable sinks via the `--sink` and `--sink-opts` options:
- `file`: Local file output
- `stdout`: Console output
- `otel`: OTLP-compatible backends

Check out [Exporters](../exporters/README.md).

### Common CLI Options
All collectors share these standard options:
- `--cluster`: Cluster identifier
- `--sink`: Output destination
- `--sink-opts`: Sink-specific configuration
- `--interval`: Seconds between collection cycles
- `--once`: Run once and exit (vs. continuous loop)
- `--log-level`: Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `--log-folder`: Directory for log files
- `--dry-run`: Test mode without publishing data
- `--chunk-size`: The maximum size in bytes of each chunk when writing data to sink.
- `--retries`: Number of retry attempts on failure

### Data Collection Loop
Most collectors use `run_data_collection_loop()` which provides:
- Interval-based scheduling
- Error handling and retries
- Graceful shutdown
- Logging integration

### Schema Validation
Data payloads use typed dataclasses for validation:
- `DevicePlusJobMetrics`, `HostMetrics` (nvml_monitor)
- `Sacct`, `SacctmgrQosPayload`, `SacctmgrUserPayload` (SLURM accounting)
- `Scontrol`, `ScontrolConfig` (SLURM control)
- `NodeData`, `SLURMLog` (SLURM monitoring)

## Adding a New Collector

Check out [Adding New Collector](../adding_new_collector.md).
