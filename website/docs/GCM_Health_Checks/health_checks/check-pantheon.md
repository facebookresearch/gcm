# check-pantheon

## Overview
Runs workloads of [Pantheon](https://github.com/pantheongpu/pantheon), an open-source (Apache-2.0) GPU diagnostics suite, on the GPUs of the node and turns its report into a health-check result. Each workload loads one part of the card, such as its memory or its arithmetic units, verifies what the card returns, and reads the card's error counters before and after the run. The check reports a card that returned wrong data, that logged uncorrectable errors, that could not finish a workload, or that throttled on temperature while it ran.

Where [memtest](memtest.md) confirms that memory can be allocated and written, this check runs pattern tests over the memory (`march_test`, `galpat`, `memory_hammer`) and can run compute workloads, so it takes longer. It is meant for the same places: before or after a job, or on a drained node.

## Dependencies

- The `pantheon` executable, version 1.2.2 or later
- A CUDA compiler (`nvcc`) on NVIDIA nodes, or `hipcc` on AMD nodes, which Pantheon uses to build its workloads for the GPUs it finds

### Installing Pantheon

```shell
# From PyPI
pipx install pantheon-gpu

# From conda-forge
conda install -c conda-forge pantheon-gpu
```

Pantheon needs no root access and no kernel module. Without a compiler it runs on a CPU backend that exercises no hardware. The check reports that case as UNKNOWN rather than as a pass.

### Binary Interface

The check runs one command per workload, in a temporary directory:

```shell
pantheon --test <workload> --duration <seconds> --mem <percent> --gpu <ids>
```

Pantheon writes its reports as JSON files to `./database/`. The check reads the row of each GPU from these reports and does not parse the text that Pantheon prints.

The workloads are listed in the [Pantheon documentation](https://pantheongpu.com/tests/).

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--workload` / `-w` | String (multiple) | `memory_read`, `march_test` | Pantheon workload to run (can specify multiple) |
| `--duration` | Integer | 30 | Seconds to run each workload |
| `--mem-percent` | Integer | 99 | Percentage of the free GPU memory that a workload may use |
| `--pantheon-bin` | Path | None | Path to the `pantheon` executable (uses PATH if not specified) |
| `--gpu-devices` / `-gpu` | Integer (multiple) | Auto-detect | GPU device IDs to test (can specify multiple). If it's called on prolog/epilog attempts reading `SLURM_JOB_GPUS`/`CUDA_VISIBLE_DEVICES` environment variables, otherwise every GPU of the node is tested |
| `--timeout` | Integer | 300 | Timeout in seconds of each workload's command |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

The timeout applies to one workload. It has to cover the duration and, on the first run on a node, the time Pantheon takes to compile its workloads, which was about 80 seconds on the machine this check was tested on.

### Build Cache
Pantheon compiles its workloads on the first run and reuses them afterwards. It keeps them in `~/.cache/pantheongpu/builds` of the user that runs the check, or in the directory that the `PANTHEON_BUILD_CACHE_DIR` environment variable names. Set the variable to a directory on the node when the home directory of that user is not writable.

## Validation Logic

### Testing Process
1. **Device selection**: The GPUs given with `--gpu-devices`, or on prolog/epilog the GPUs allocated to the job, or every GPU of the node
2. **Per-workload run**: One `pantheon` command per workload, which runs the workload on the selected GPUs
3. **Report parsing**: One result row per GPU and workload is read from Pantheon's JSON reports
4. **Per-row assessment**: Each row gets an exit code, see below
5. **Exit code determination**: Use maximum exit code across all GPUs and workloads

### Per-Row Assessment

| Finding in the row | Exit Code |
|--------------------|-----------|
| A memory test (`march_test`, `galpat`, `memory_hammer`, `memory_retention`, `memory_retention_bake`, `ras_validator`) failed | CRITICAL |
| Any other workload did not complete | CRITICAL |
| The error counters report uncorrectable errors during the run | CRITICAL |
| The card throttled on temperature, or reached 90 C | WARN |
| The error counters report correctable errors during the run | WARN |
| None of the above | OK |

A PCIe link that changed its power state during the run (`l0_to_recovery`) is not counted as an error, since healthy hardware does this.

### CUDA_VISIBLE_DEVICES Handling
The check unsets `CUDA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES` and `ROCR_VISIBLE_DEVICES` while Pantheon runs, for the same reason as [memtest](memtest.md):
- Device IDs from `SLURM_JOB_GPUS` (e.g., `2,3,5`) are already absolute physical IDs
- Unsetting ensures `--gpu 2` tests physical GPU 2, not a remapped device
- Restored automatically after the run

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All workloads passed on all GPUs |
| **OK (0)** | Called on prolog/epilog for a job that has no GPU allocated |
| **WARN (1)** | Thermal throttling, a temperature of 90 C or more, or correctable errors |
| **WARN (1)** | The command raised an exception or timed out |
| **CRITICAL (2)** | A workload failed or did not complete |
| **CRITICAL (2)** | Uncorrectable errors were counted during the run |
| **UNKNOWN (3)** | Pantheon wrote no report |
| **UNKNOWN (3)** | Pantheon ran on its CPU backend, no hardware was tested |
| **UNKNOWN (3)** | The allocated GPUs cannot be read from the environment |

## Usage Examples

### Basic Check
```shell
health_checks check-pantheon --sink stdout [CLUSTER] app
```
Runs `memory_read` and `march_test` for 30 seconds each on every GPU of the node.

### Test the GPUs of a Job
```shell
health_checks check-pantheon --sink stdout [CLUSTER] prolog
```
Uses `SLURM_JOB_GPUS` to find the allocated GPUs.

### Test Specific GPUs with Selected Workloads
```shell
health_checks check-pantheon \
  --workload march_test \
  --workload galpat \
  --workload tensor_virus \
  --duration 60 \
  --gpu-devices 0 \
  --gpu-devices 1 \
  --sink stdout \
  [CLUSTER] \
  app
```

### Custom Path with Verbose Output
```shell
health_checks check-pantheon \
  --pantheon-bin /opt/pantheon/bin/pantheon \
  --timeout 600 \
  --verbose-out \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

With `--verbose-out` the check prints one line per GPU and workload:

```
OK - check pantheon. GPU 0 memory_read: 341.178 GB/s
GPU 0 march_test: 2909050000.0 march-ops/s
```
