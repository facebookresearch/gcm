---
sidebar_position: 1
---

# Do Nothing

The Do Nothing exporter is a placeholder sink that discards all monitoring data and health check results without performing any action. It implements the sink interface but does not write, store, or transmit data anywhere.

## Overview

The Do Nothing exporter is registered with the identifier `do_nothing` and is primarily used for:

- **Testing and development**: Running monitoring commands or health checks without generating output
- **Dry runs**: Validating command syntax and configuration without side effects
- **Placeholder configuration**: Temporarily disabling data export while maintaining valid configuration

## Configuration

### Available Options

The Do Nothing exporter accepts no configuration options (`--sink-opt` is not required).

### Basic Usage

```shell
# Use with monitoring commands
gcm slurm_monitor --sink=do_nothing --once

# Use with health checks
health_checks check-nvidia-smi fair_cluster prolog --sink=do_nothing
```

### Configuration File

```toml
[gcm.slurm_monitor]
...
sink = "do_nothing"
```

## Use Cases

### Testing Command Execution

When developing or testing monitoring scripts, use the Do Nothing sink to verify command execution without generating output files or logs:

```shell
# Test that the command runs without errors
gcm slurm_monitor --sink=do_nothing --once
```

### Development and Debugging

During development of new monitoring components or health checks, use the Do Nothing sink to focus on data collection logic without worrying about output formatting:

```shell
# Test new monitoring logic
gcm custom_monitor --sink=do_nothing --once
```

### Temporary Disabling

In production configurations, temporarily switch to the Do Nothing sink to disable data export without removing or commenting out configuration:

```toml
# Temporarily disable export
[gcm.slurm_monitoring]
...
# sink = "otel"  # Commented out
sink = "do_nothing"  # Temporary
```
