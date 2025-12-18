# check-nccl

## Overview
Validates NCCL (NVIDIA Collective Communications Library) performance and correctness by running distributed GPU communication tests. Supports single-node and pairwise multi-node testing using MPI to orchestrate collective operations (all_reduce, all_gather, alltoall). Measures average bus bandwidth and compares against configurable thresholds to detect network degradation or GPU interconnect issues.

## Requirements

- NVIDIA GPUs on all tested nodes
- NVIDIA driver and CUDA toolkit
- MPI implementation (OpenMPI)
- Network fabric configured (InfiniBand, RoCE, or TCP/IP)
- Passwordless SSH between nodes (for MPI)
- NCCL library installed

### Required Binaries
Located in `--nccl-tdir`:
- `all_reduce_perf` - For `--op all_reduce`
- `all_gather_perf` - For `--op all_gather`
- `alltoall_perf` - For `--op alltoall`

**Installation**:
```shell
# Clone and build NCCL tests
git clone https://github.com/NVIDIA/nccl-tests.git
cd nccl-tests
make MPI_HOME=/path/to/mpirun CUDA_HOME=/path/to/cuda/12.0 NCCL_HOME=/path/to/NCCL/2.21.5-1
# Binaries in: ./build/
```

### MPI Requirements
- `mpirun` or compatible launcher in PATH
- MPI can discover and connect to all hosts in hostlist
- Sufficient process slots per node (typically = GPU count)

**Verification**:
```shell
# Test MPI connectivity
mpirun --host node1:8,node2:8 --np 16 hostname

# Check available slots
mpirun --host node1 --np 1 cat /proc/cpuinfo | grep processor | wc -l
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--single` | Flag | True | Single-node NCCL testing (default) |
| `--pairwise` / `--pairwise-exhaustive` | Flag | False | Test all possible node pairs from hostlist |
| `--pairwise-quick` | Flag | False | Test each node once (pairs: even-odd indices) |
| `--mpi-binpath` | Path | `mpirun` | Path to `mpirun` binary |
| `--mpi-opts` | String | `-mca coll_hcoll_enable 0 --bind-to numa` | Options passed to `mpirun` |
| `--np` / `-n` | Integer | Auto-calculated | Number of MPI processes (defaults to nodes × GPUs) |
| `--gpus-per-node` | Integer | 8 | GPUs per node (used for auto-calculating `-np`) |
| `--hostlist` | String | localhost | Node list (required for pairwise modes) |
| `--export` / `-x` | String (multiple) | `NCCL_IB_PCI_RELAXED_ORDERING=1`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `NCCL_SOCKET_IFNAME=eth0`, `NCCL_DEBUG=WARN` | Environment variables to export to MPI processes |
| `--nccl-tdir` | Path | **Required** | Directory containing NCCL test binaries |
| `--nccl-topts` | String | `-g 1 -b 32M -e 1G -f 2` | NCCL test options (see NCCL tests docs) |
| `--op` / `-p` | Choice (multiple) | **Required** | Operations: `all_gather`, `all_reduce`, `alltoall` |
| `--nvlink/--no-nvlink` | Flag | `--no-nvlink` | Enable/disable NVLink (disables P2P and SHM if off) |
| `--critical-threshold` | Float | **Required** | Critical exit if if avg bus bw value < threshold (in GB/s) |
| `--warn-threshold` | Float | None | Warning exit if if avg bus bw value < threshold (in GB/s) |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

### Hostlist Parsing
Uses SLURM-style nodelist expansion:
```shell
node[1-3]       → node1, node2, node3
gpu[01-04]      → gpu01, gpu02, gpu03, gpu04
host1,host2     → host1, host2
```

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All tests passed thresholds |
| **WARN (1)** | Test execution failed |
| **WARN (1)** | Bandwidth parsing failed |
| **WARN (1)** | Below warn threshold |
| **CRITICAL (2)** | Below critical threshold |

**Aggregation**: If any test returns CRITICAL, overall exit is CRITICAL. Else if any WARN, overall exit is WARN. Else OK.

## Usage Examples

### Single-Node NVLink Test
```shell
health_checks check-nccl \
  --single \
  --nccl-tdir /opt/nccl-tests/build \
  --op all_reduce \
  --nvlink \
  --critical-threshold 200 \
  --warn-threshold 250 \
  --sink stdout \
  [CLUSTER] \
  app
```
Tests intra-node NVLink bandwidth, expecting \>250 GB/s for OK, 200-250 for WARN, \<200 for CRITICAL.

### Pairwise Network Test (All Pairs)
```shell
health_checks check-nccl \
  --pairwise \
  --hostlist node[1-8] \
  --nccl-tdir /opt/nccl-tests/build \
  --op all_reduce \
  --op all_gather \
  --no-nvlink \
  --critical-threshold 50 \
  --warn-threshold 80 \
  --gpus-per-node 8 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
Tests all 28 node pairs (C(8,2)) with 2 operations each = 56 total tests.

### Pairwise Quick Test
```shell
health_checks check-nccl \
  --pairwise-quick \
  --hostlist node[1-16] \
  --nccl-tdir /opt/nccl-tests/build \
  --op all_reduce \
  --critical-threshold 40 \
  --timeout 600 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
Tests 8 node pairs (even-odd pairing), faster than exhaustive.

### Custom MPI Configuration
```shell
health_checks check-nccl \
  --single \
  --nccl-tdir /opt/nccl-tests/build \
  --op alltoall \
  --critical-threshold 100 \
  --mpi-binpath /usr/local/bin/mpirun \
  --mpi-opts "-mca btl tcp,self -mca btl_tcp_if_include eth0" \
  --export NCCL_DEBUG=INFO \
  --export NCCL_IB_HCA=mlx5 \
  --nccl-topts "-g 1 -b 8M -e 2G -f 2 -n 100" \
  --sink stdout \
  [CLUSTER] \
  app
```

### Multi-Operation Test with Custom Thresholds
```shell
health_checks check-nccl \
  --pairwise-quick \
  --hostlist gpu[01-32] \
  --nccl-tdir /opt/nccl-tests/build \
  --op all_reduce \
  --op all_gather \
  --op alltoall \
  --nvlink \
  --critical-threshold 150 \
  --warn-threshold 200 \
  --gpus-per-node 8 \
  --np 128 \
  --timeout 900 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```

### Debug Mode with Verbose Output
```shell
health_checks check-nccl \
  --single \
  --nccl-tdir /opt/nccl-tests/build \
  --op all_reduce \
  --critical-threshold 50 \
  --log-level DEBUG \
  --verbose-out \
  --export NCCL_DEBUG=INFO \
  --sink stdout \
  [CLUSTER] \
  app
```
