# nvlink

## Overview
Monitors NVLink errors and status using NVIDIA Data Center GPU Manager (DCGM). Detects CRC errors, replay/recovery errors, and link connectivity issues across GPUs.

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--check` / `-c` | Multiple | - | Checks to perform: `nvlink_errors`, `nvlink_status` (required, can specify both) |
| `--gpu_num` / `-g` | Integer | 8 | Number of GPUs to check |
| `--data_error_threshold` | Integer | 0 | CRC Data Error threshold (errors to tolerate) |
| `--flit_error_threshold` | Integer | 0 | CRC FLIT Error threshold |
| `--recovery_error_threshold` | Integer | 0 | Recovery Error threshold |
| `--replay_error_threshold` | Integer | 0 | Replay Error threshold |
| `--host` | String | localhost | DCGM host endpoint to connect to |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Check Types

### nvlink_errors
Monitors NVLink error counts per GPU link:
- **CRC Data Error** - Data corruption errors
- **CRC FLIT Error** - Flow control unit errors
- **Replay Error** - Link replay requests
- **Recovery Error** - Link recovery events

For each GPU (0 to `gpu_num-1`), checks all links and compares error counts against thresholds.

### nvlink_status
Monitors NVLink link status for all GPUs:
- **U (Up)** - Link is operational
- **D (Down)** - Link is down
- **X (Disabled)** - Link is disabled

Detects any down or disabled links across all GPUs.

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All NVLink checks passed |
| **WARN (1)** | DCGM command failed to execute |
| **WARN (1)** | Output parsing failed |
| **CRITICAL (2)** | NVLink errors exceed threshold |
| **CRITICAL (2)** | NVLink links are down or disabled |

## Usage Examples

### Check NVLink Errors
```shell
health_checks check-dcgmi nvlink \
  --check nvlink_errors \
  --gpu_num 8 \
  [CLUSTER] \
  app
```

### Check NVLink Status
```shell
health_checks check-dcgmi nvlink \
  --check nvlink_status \
  --gpu_num 8 \
  [CLUSTER] \
  prolog
```

### Combined Checks
```shell
health_checks check-dcgmi nvlink \
  --check nvlink_errors \
  --check nvlink_status \
  --gpu_num 8 \
  [CLUSTER] \
  epilog
```

### With Error Thresholds
```shell
health_checks check-dcgmi nvlink \
  --check nvlink_errors \
  --gpu_num 8 \
  --data_error_threshold 10 \
  --flit_error_threshold 5 \
  --replay_error_threshold 100 \
  --recovery_error_threshold 50 \
  [CLUSTER] \
  app
```

### Debug Mode
```shell
health_checks check-dcgmi nvlink \
  --check nvlink_errors \
  --gpu_num 8 \
  --log-level DEBUG \
  --verbose-out \
  [CLUSTER] \
  app
```
