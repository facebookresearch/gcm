---
sidebar_position: 4
---

# OpenTelemetry (OTEL)

The OpenTelemetry exporter sends monitoring data and health check results to any OpenTelemetry Protocol (OTLP) compatible backend using HTTP. It supports both logs and metrics with standard OTLP formatting.

:::info OpenTelemetry Standard
This exporter uses the official OpenTelemetry Python SDK and follows the OpenTelemetry conventions. This means **standard OTEL environment variables** documented in the [OpenTelemetry specification](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/) should be respected by the exporter.
:::

## Configuration

### Authentication and Endpoint

The exporter requires an OTLP endpoint. You can provide this in two ways:

#### Environment Variables (Recommended)

```shell
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_TIMEOUT="30"
gcm slurm_monitor --sink=otel --once
```

#### Command Line Options

```shell
gcm slurm_monitor \
  --sink=otel \
  --sink-opt otel_endpoint=http://localhost:4318 \
  --sink-opt otel_timeout=30 \
  --once
```

### Available Options

| Option | Required | Description |
|--------|----------|-------------|
| `otel_endpoint` | Conditional* | OTLP HTTP endpoint base URL |
| `otel_timeout` | Conditional** | Request timeout in seconds |
| `log_resource_attributes` | No | Key-value pairs for log resource metadata |
| `metric_resource_attributes` | No | Key-value pairs for metric resource metadata |

\* Required if `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable is not set.

\** Required if `OTEL_EXPORTER_OTLP_TIMEOUT` environment variable is not set.

### Basic Usage

```shell
# Send to local OpenTelemetry Collector
gcm slurm_monitor --sink=otel --sink-opt otel_endpoint=http://localhost:4318 --once

# Send to remote OTLP endpoint
gcm slurm_monitor \
  --sink=otel \
  --sink-opt otel_endpoint=https://otel-collector.example.com:4318 \
  --once
```

### Configuration File

```toml
[gcm.slurm_monitor]
sink = "otel"
sink_opts = [
  "otel_endpoint=http://localhost:4318",
  "otel_timeout=30",
# (Optional) Resource Attributes are attached to all logs or metrics.
  "log_resource_attributes={'environment': 'production', 'cluster': 'gpu-cluster-a', 'region': 'us-west-2'}",
  "metric_resource_attributes={'environment': 'production', 'cluster': 'gpu-cluster-a', 'region': 'us-west-2'}",
]
```

## OTLP Endpoints

The exporter automatically appends the appropriate path to the base endpoint:

- **Logs**: `{otel_endpoint}/v1/logs`
- **Metrics**: `{otel_endpoint}/v1/metrics`

## Metrics

### Metric Type

The exporter uses **OpenTelemetry Gauge instruments** for all numeric metrics. Gauges represent point-in-time values and are appropriate for metrics like GPU utilization, temperature, or job counts.

### Background Export

Metrics export happens **automatically in the background** by the OpenTelemetry SDK's `PeriodicExportingMetricReader`. This means:

- The exporter collects metric values as they're reported
- The SDK batches and exports metrics at a fixed interval (default: **60 seconds**)
- Even if you update a gauge multiple times, it will only be exported at the configured interval
- The most recent gauge value at export time is sent to the backend

This background export can be controlled via standard OpenTelemetry environment variables:
- `OTEL_METRIC_EXPORT_INTERVAL` - Controls how often metrics are exported (default: 60000 milliseconds)
- `OTEL_METRIC_EXPORT_TIMEOUT` - Controls export timeout (default: 5000 milliseconds)

**Example: Adjusting export interval**
```shell
# Export metrics every 30 seconds instead of 60
export OTEL_METRIC_EXPORT_INTERVAL=30000
gcm slurm_monitor --sink=otel --sink-opt otel_endpoint=http://localhost:4318
```

:::tip
If your monitoring loop runs more frequently than the export interval (e.g., every 10 seconds), the gauge will be updated multiple times but only the latest value will be exported when the 60-second interval elapses.

If this impacts your metrics, feel free to [open a feature request](https://github.com/facebookresearch/gcm/issues) to support `metric_export_interval` as one of the options to the exporter.
:::

## Use Cases

### Local Development with OpenTelemetry Collector

Run a local [OTEL collector](https://opentelemetry.io/docs/collector/), backends for metrics and logs, and send data to it:

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

exporters:
  logging:
    loglevel: debug
  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    logs:
      receivers: [otlp]
      exporters: [logging]
    metrics:
      receivers: [otlp]
      exporters: [prometheus]
```

```shell
# Start OTEL collector
otelcol --config=otel-collector-config.yaml

# Send data from GCM
gcm slurm_monitor --sink=otel --sink-opt otel_endpoint=http://localhost:4318 --once
```

### Production with Managed OTLP Backend

Send to a managed observability platform:

```toml
[gcm.slurm_monitor]
...
sink = "otel"
sink_opts = [
  "otel_endpoint=https://otlp.observability-platform.com",
  "otel_timeout=60",
  "log_resource_attributes={'environment': 'production', 'cluster': 'gpu-cluster-a', 'region': 'us-west-2'}",
  "metric_resource_attributes={'environment': 'production', 'cluster': 'gpu-cluster-a', 'region': 'us-west-2'}",
]
```

### Cloud-Native Kubernetes Deployment

Deploy as a sidecar with OTEL collector:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: gcm-config
data:
  config.toml: |
    [gcm.slurm_monitor]
    ...
    sink = "otel"
    sink_opts = [
    "otel_endpoint=http://localhost:4318",
    "otel_timeout=60",
    "log_resource_attributes={'environment': 'production', 'k8s.namespace': 'monitoring', 'k8s.pod': '${POD_NAME}'}",
    "metric_resource_attributes={'environment': 'production', 'k8s.namespace': 'monitoring', 'k8s.pod': '${POD_NAME}'}",
    ]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gcm-monitor
spec:
  template:
    spec:
      containers:
      - name: gcm
        image: gcm:latest
        command: ["gcm", "slurm_monitor", "--config=/etc/gcm/config.toml"]
        volumeMounts:
        - name: config
          mountPath: /etc/gcm
      - name: otel-collector
        image: otel/opentelemetry-collector:latest
        args: ["--config=/etc/otel/config.yaml"]
      volumes:
      - name: config
        configMap:
          name: gcm-config
```
