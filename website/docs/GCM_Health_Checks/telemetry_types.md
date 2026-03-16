---
sidebar_position: 3
---

# Telemetry Types

GCM supports two types of telemetry: LOG and METRIC. The convention is:

- `LOG` for tabular data.
- `METRIC` for timeseries.

Health checks that publish telemetry use log schemas such as **HealthCheckLog**. For AMD communication checks ([check_rccl](health_checks/check-rccl.md), [check_mori](health_checks/check-mori.md)), the **CommunicationCheckLog** schema is used, which extends the base health-check log with optional bandwidth/latency fields (`bandwidth_gbps`, `latency_us`, etc.).

Exporters often handle telemetry types differently based on their own requirements.

For example, OpenTelemetry has different APIs to export `LOG`s and `METRIC`s, and these will be reflected in the [exporter implementation](https://github.com/facebookresearch/gcm/blob/main/gcm/exporters/otel.py).
