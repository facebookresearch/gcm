---
sidebar_position: 1
---

# Getting Started

GCM Health Checks is a Python CLI with a suite of [Health Checks](#available-health-checks)

<img src="/gcm/img/gcm_health_checks.png" style={{ maxHeight: '300px', display: 'block', margin: '0 auto' }} />

## Quick Start Guide

### Requirements

- Python 3.10+
- System utilities (varies by check: `nvidia-smi`, `dcgmi`, `sensors`, etc.)
- Slurm (for job scheduler integration checks)

### Installation

```shell
pip install gpucm
```

#### Install from Github

```shell
# Latest main
pip install --upgrade git+ssh://git@github.com:facebookresearch/gcm.git@main

# Specific release
pip install --upgrade git+ssh://git@github.com:facebookresearch/gcm.git@<release>
```

### CLI

After installing gcm you should be able to call health checks via the CLI:

```shell
$ health_checks --help
Usage: health_checks [OPTIONS] COMMAND [ARGS]...

  GPU Cluster Monitoring: Large-Scale AI Research Cluster Monitoring.

Options:
  --features-config FILE  Path parameter for the features config file, to load
                          feature values.
  --config FILE           Load option values from table 'health_checks' in the
                          given TOML config file. A non-existent path or
                          '/dev/null' are ignored and treated as empty tables.
                          [default: /etc/fb-healthchecks/config.toml]
  -d, --detach            Exit immediately instead of waiting for GCM to run.
  --version               Show the version and exit.
  --help                  Show this message and exit.

Commands:
  check-airstore        AIRStore-based application readiness checks
  check-authentication  authentication based checks.
  check-blockdev        Check block devices against the manifest file
  check-dcgmi           dcgmi based commands.
  check-ethlink         Check eth links against the manifest file
  check-hca             Check if HCAs are present and count matches the...
  check-ib              ib status checks.
  check-ipmitool        ipmitool based checks.
  check-nccl            Run NCCL tests to check both the performance and...
  check-node            various node based checks.
  check-nvidia-smi      Perform nvidia-smi checks to assess the state of...
  check-pci             Check pci subsystem against the manifest file.
  check-process         A collection of process related checks.
  check-processor       processor based checks.
  check-sensors         Invoke ipmi-sensors and return the output.
  check-service         check the system services.
  check-ssh-certs       Check hostkeys against ipa certs.
  check-storage         storage based checks.
  check-syslogs         syslog based checks.
  check-telemetry       Perform only the telemetry for health-checks
  cuda                  A collection of CUDA related checks.
```

### Available Health Checks

Check out [GCM Health Checks documentation](./health_checks/README.md).

### Configuration Files

GCM Health Checks supports TOML configuration files to simplify parameter management:

```toml
# FILE: health_check_config.toml

[health_checks.check-nvidia-smi]
timeout = 60
sink = "otel"
sink_opts = [
  "otel_endpoint=https://otlp.observability-platform.com",
  "otel_timeout=30",
]
```

You can then invoke checks with the config file:
```shell
# Using config file
health_checks --config=/etc/health_check_config.toml check-nvidia-smi gpu-present [CLUSTER] app

# CLI arguments override config file values
health_checks --config=/etc/health_check_config.toml check-nvidia-smi gpu-present --timeout=30 [CLUSTER] app
```

### License

GCM Health Checks is licensed under the [MIT License](https://github.com/facebookresearch/gcm/blob/main/gcm/LICENSE).
