# Exporters

:::tip

Exporters are shared between [GCM Monitoring](../../GCM_Monitoring/getting_started.md) and [GCM Health Checks](../getting_started.md).

:::

Exporters (also called "sinks") are the output layer for GCM's monitoring and health check data. They provide a flexible, plugin-based system for sending collected data to various destinations, from simple terminal output to sophisticated observability platforms.

## Overview

GCM uses a unified exporter system that is **shared between both monitoring and health check services**. This means any exporter you configure can be used with:
- **Monitoring commands** (`gcm slurm_monitor`, `gcm nvml_monitor`, etc.)
- **Health check commands** (`health_checks check-dcgmi`, `health_checks check-nvidia-smi`, etc.)

## Available Exporters

GCM includes several built-in exporters for different use cases:

| Exporter | Identifier | Purpose |
|----------|-----------|---------|
| [Do Nothing](do_nothing.md) | `do_nothing` | Testing and dry runs |
| [File](file.md) | `file` | Local file storage |
| [Graph API](graph_api.md) | `graph_api` | Meta's internal backends |
| [OpenTelemetry](otel.md) | `otel` | OTLP-compatible backends |
| [Stdout](stdout.md) | `stdout` | Terminal output |

## Plugin System

GCM's exporter system is designed as a plugin architecture that makes it easy to add new exporters without modifying core code.

To add a new exporter check out [Adding New Exporter](../adding_new_exporter.md).

## Using Exporters

### Command Line

Specify an exporter using the `--sink` flag and configure it with `--sink-opt`:

```shell
# Use stdout exporter
gcm slurm_monitor --sink=stdout --once

# Use file exporter with path option
gcm slurm_monitor --sink=file --sink-opt file_path=/var/log/gcm/data.json --once

# Use OTEL exporter with multiple options
gcm slurm_monitor \
  --sink=otel \
  --sink-opt otel_endpoint=http://localhost:4318 \
  --sink-opt otel_timeout=30 \
  --once
```
