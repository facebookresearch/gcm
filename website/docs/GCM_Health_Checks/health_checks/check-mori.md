# check-mori

## Overview
Validates **MORI (Modular RDMA Interface)** on AMD GPU nodes. MORI provides a modular RDMA interface for GPU communication. The check can run a **smoke test** (installed `mori` package only, no repo clone) or full pytest from a pre-deployed MORI repo (e.g. `dispatch_combine`, `io` tests). Telemetry is published via the **CommunicationCheckLog** schema with optional bandwidth/latency metrics when running benchmarks.

## Requirements

- AMD GPU node with MORI stack (e.g. `pip install mori` for smoke)
- For full tests: MORI repo deployed at `--mori-repo` path

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--mori-repo` | Path | None | Path to pre-deployed MORI repo for full pytest. If omitted, smoke only. |
| `--mori-test` | Choice | smoke | Test to run: `smoke`, `dispatch_combine`, `io`, or `both` (latter require `--mori-repo`). |
| `--timeout` | Integer | 300 | Command execution timeout (seconds) |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | /var/log/fb-monitoring | Log directory |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | MORI smoke or selected test passed |
| **WARN (1)** | Test execution failed or exception |
| **CRITICAL (2)** | MORI repo path missing or test path not found |

## Usage Examples

### Smoke test (no repo; uses installed mori package)
```shell
health_checks check_mori [CLUSTER] prolog --sink do_nothing
```

### Full pytest from pre-deployed MORI repo
```shell
health_checks check_mori [CLUSTER] prolog \
  --mori-repo /opt/mori \
  --mori-test dispatch_combine \
  --sink file --sink-opts file_path=/var/log/mori_check.json
```

### IO test with telemetry
```shell
health_checks check_mori [CLUSTER] prolog \
  --mori-repo /opt/mori \
  --mori-test io \
  --sink stdout
```

## Telemetry

When a sink other than `do_nothing` is used, check_mori publishes telemetry using the **CommunicationCheckLog** schema. For benchmark runs, optional fields such as `bandwidth_gbps`, `latency_us`, `dispatch_bw_gbps`, and `combine_bw_gbps` may be populated (best-effort parsing from benchmark stdout).
