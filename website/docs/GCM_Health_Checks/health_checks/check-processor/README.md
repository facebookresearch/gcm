# check-processor

CPU and memory subsystem validation suite with health checks for processor frequency, governor settings, memory configuration, fragmentation, and clocksource.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [processor-freq](./processor-freq.md) | CPU frequency validation | Verify CPU frequency meets minimum threshold |
| [cpufreq-governor](./cpufreq-governor.md) | Governor settings validation | Ensure consistent governor across all CPU cores |
| [check-mem-size](./check-mem-size.md) | Memory configuration validation | Verify DIMM count and total memory size |
| [check-buddyinfo](./check-buddyinfo.md) | Memory fragmentation detection | Check for sufficient large memory blocks |
| [check-clocksource](./check-clocksource.md) | Clocksource validation | Verify system clocksource configuration |

## Quick Start

```shell
# CPU frequency check
health_checks check-processor processor-freq --sink stdout [CLUSTER] app

# Governor validation
health_checks check-processor cpufreq-governor --sink stdout [CLUSTER] app

# Memory size check
health_checks check-processor check-mem-size --sink stdout [CLUSTER] app

# Memory fragmentation check
health_checks check-processor check-buddyinfo --sink stdout [CLUSTER] app

# Clocksource validation
health_checks check-processor check-clocksource --expected-source tsc --sink stdout [CLUSTER] app
```
