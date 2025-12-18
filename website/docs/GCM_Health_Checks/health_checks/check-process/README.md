# check-process

Process-related health checks for D-state, running process, and zombie detection.

## Subcommands

| Subcommand | Purpose | Key Feature |
|------------|---------|-------------|
| [`check-dstate`](./check-dstate.md) | Detects processes stuck in uninterruptible sleep (D-state) | Age-based threshold detection with process filtering |
| [`check-running-process`](./check-running-process.md) | Validates that specified processes are currently running | Multi-process verification with detailed output |
| [`check-zombie`](./check-zombie.md) | Detects zombie (defunct) processes | Persistent zombie detection with configurable thresholds |

## Quick Start

### Detect D-state Processes
```shell
health_checks check-process check-dstate \
  --sink stdout \
  [CLUSTER] \
  app
```

### Check Running Processes
```shell
health_checks check-process check-running-process \
  --process-name nvidia-smi \
  --sink stdout \
  [CLUSTER] \
  app
```

### Detect Zombie Processes
```shell
health_checks check-process check-zombie \
  --sink stdout \
  [CLUSTER] \
  app
```
