# check-dcgmi

GPU diagnostics and NVLink validation using NVIDIA Data Center GPU Manager (DCGM).

## Subcommands

| Subcommand | Purpose | Key Feature |
|------------|---------|-------------|
| [`diag`](./diag.md) | Hardware diagnostics across multiple test levels | Deployment, integration, hardware, and stress testing with category exclusion |
| [`nvlink`](./nvlink.md) | NVLink error and status monitoring | Error threshold validation and link status detection |

## Quick Start

### Run GPU Diagnostics
```shell
health_checks check-dcgmi diag \
  --diag_level 1 \
  [CLUSTER] \
  app
```

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
  app
```
