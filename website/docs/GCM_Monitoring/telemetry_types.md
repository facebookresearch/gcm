---
sidebar_position: 2
---

# Telemetry Types

GCM supports two types of telemetry: LOG and METRIC. The convention is:

- `LOG` for tabular data.
- `METRIC` for timeseries.

Exporters often handle telemetry types differently based on their own requirements.

For example, OpenTelemetry has different APIs to export `LOG`s and `METRIC`s, and these will be reflected in the [exporter implementation](https://github.com/facebookresearch/gcm/blob/main/gcm/exporters/otel.py).
