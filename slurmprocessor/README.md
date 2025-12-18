<!--
Copyright (c) Meta Platforms, Inc. and affiliates.
All rights reserved.
-->
# Slurm Processor

An [OpenTelemetry](https://github.com/open-telemetry/opentelemetry-collector) processor for enriching telemetry data with Slurm metadata.

## Overview

The Slurm Processor is designed to enhance OpenTelemetry telemetry data (traces, metrics, and logs) with Slurm job information. It identifies the Slurm jobs associated with specific GPUs and adds relevant metadata such as job IDs, user names, partitions, and other Slurm-specific attributes to the telemetry data.

This processor is particularly useful in high-performance computing environments where correlating system telemetry with Slurm job information is important for monitoring.

We've found at Meta that this processor is mostly useful for Metrics data.

## Getting Started

Slurm Processor is a component of the [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector). To use it, you'll need to build a [custom OpenTelemetry Collector](https://opentelemetry.io/docs/collector/custom-collector/).

1. Add the below to the [builder-config.yaml](https://opentelemetry.io/docs/collector/custom-collector/#step-2---create-a-builder-manifest-file) file:

```yaml
...
processors:
  - gomod:
      path/to/gcm/slurmprocessor
...
```

2. Run the following command to build the OpenTelemetry Collector binary:

```shell
./ocb --config builder-config.yaml
```

3. Add the below to your [collector-config.yaml](https://opentelemetry.io/docs/collector/custom-collector/#step-3---create-a-collector-configuration-file) file:

```yaml
...
processors:
  slurm:
    # The number of seconds to cache the results for Slurm calls in memory
    # Affects the number of misattributed Slurm metadata at the beginning and end of the job lifetime
    # low values here could overwhelm slurmctld, be careful
    cache_duration: 60

    # Path to the file where it caches results
    cache_filepath: '/tmp/slurmprocessor_cache.json'

    # Boolean that decides whether or not it queries slurmctld
    query_slurmctld: false
...
service:
  pipelines:
    metrics:
      receivers:
      - receiver1
      processors:
      - slurm # <-- Add this line
      exporters:
      - exporter1
...
```

## Dependencies

- [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector)
- [shelper](../shelper) go package for Slurm metadata retrieval

## License

slurmprocessor is licensed under the [Apache 2.0](./LICENSE) license.
