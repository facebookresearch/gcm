# check-rccl

## Overview
Validates RCCL (ROCm Communication Collectives Library) performance and correctness on **AMD GPU nodes** by running distributed GPU communication tests. Analogous to [check-nccl](check-nccl.md) for NVIDIA. Supports single-node and pairwise multi-node testing using MPI. Measures average bus bandwidth and compares against configurable thresholds. Telemetry is published via the `CommunicationCheckLog` schema (bandwidth/latency metrics).

## Requirements

- AMD GPUs and ROCm on all tested nodes
- MPI implementation (OpenMPI)
- Network fabric configured (InfiniBand, RoCE, or TCP/IP)
- Passwordless SSH between nodes (for MPI)
- RCCL tests built from [ROCm/rccl-tests](https://github.com/ROCm/rccl-tests)

### Required Binaries
Located in `--rccl-tdir`:
- `all_reduce_perf` – for `-p all_reduce`
- `all_gather_perf` – for `-p all_gather`
- `alltoall_perf` – for `-p alltoall`

**Installation**:
```shell
# Clone and build RCCL tests
git clone https://github.com/ROCm/rccl-tests.git
cd rccl-tests
make MPI_HOME=/path/to/mpirun HIP_HOME=/path/to/rocm
# Binaries in: ./build/
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--single` | Flag | True | Single-node RCCL testing |
| `--pairwise` | Flag | False | Test all node pairs from hostlist |
| `--pairwise-quick` | Flag | False | Test each node once (even-odd pairs) |
| `--mpi-binpath` | Path | `mpirun` | Path to `mpirun` binary |
| `--mpi-opts` | String | (see help) | Options passed to `mpirun` |
| `--gpus-per-node` | Integer | 8 | GPUs per node |
| `--hostlist` | String | Required for pairwise | Node list (SLURM-style expansion supported) |
| `--export` / `-x` | String (multiple) | HSA_FORCE_FINE_GRAIN_PCIE=1, GPU_DEVICE_ORDINAL=PCI_BUS_ID, NCCL_SOCKET_IFNAME=eth0, etc. | Environment variables for MPI processes |
| `--rccl-tdir` | Path | **Required** | Directory containing RCCL test binaries |
| `--rccl-topts` | String | `-g 1 -b 32M -e 1G -f 2` | RCCL test options |
| `--op` / `-p` | Choice (multiple) | **Required** | Operations: `all_gather`, `all_reduce`, `alltoall` |
| `--critical-threshold` | Float | **Required** | Critical exit if avg bus bw (GB/s) &lt; threshold |
| `--warn-threshold` | Float | None | Warning exit if avg bus bw &lt; threshold |
| `--timeout` | Integer | 300 | Command execution timeout (seconds) |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All tests passed thresholds |
| **WARN (1)** | Test execution failed or below warn threshold |
| **CRITICAL (2)** | Below critical threshold |

## Usage Examples

### Single-Node all_reduce
```shell
health_checks check_rccl [CLUSTER] prolog \
  -p all_reduce \
  --rccl-tdir /opt/rccl-tests/build/ \
  --critical-threshold 18 \
  --sink do_nothing
```

### Pairwise with hostlist
```shell
health_checks check_rccl [CLUSTER] prolog \
  -p all_reduce \
  --pairwise \
  --hostlist node-[1-4] \
  --rccl-tdir /opt/rccl-tests/build/ \
  --critical-threshold 100 \
  --sink file --sink-opts file_path=/var/log/rccl_check.json
```

### Pairwise-quick (e.g. inside SLURM job)
```shell
health_checks check_rccl [CLUSTER] prolog \
  -p all_reduce \
  --pairwise-quick \
  --hostlist=$SLURM_JOB_NODELIST \
  --rccl-tdir /opt/rccl-tests/build/ \
  --critical-threshold 100 \
  --sink do_nothing
```

## Telemetry

When a sink other than `do_nothing` is used, check_rccl publishes telemetry using the **CommunicationCheckLog** schema, which includes optional fields such as `bandwidth_gbps` and `latency_us` for correlation with other AMD communication checks (e.g. check_mori).
