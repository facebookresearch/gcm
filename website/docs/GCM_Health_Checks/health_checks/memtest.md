# memtest

## Overview
Validates GPU memory integrity by allocating and testing specified memory blocks on NVIDIA GPUs using the `cudaMemTest` binary. Executes tests concurrently across multiple GPUs to efficiently detect memory defects, ECC errors, or allocation failures that could impact compute workloads.

## Dependencies

- `cudaMemTest` binary

### Building cudaMemTest

The GCM repository includes a CUDA-based memory testing utility that can be built and used with this health check.

**Prerequisites**:
- NVIDIA CUDA Toolkit (11.2 or later)
- GCC compiler
- NVIDIA GPU with compute capability support

**Build Instructions**:
```shell
# Navigate to the cuda directory
cd gcm/health_checks/cuda/

# Build the binary using make
make

# The binary will be created as cudaMemTest in the current directory
```

**Customizing CUDA Path** (if needed):
```shell
# Edit Makefile to update CUDA_PATH or override via command line
make CUDA_PATH=/path/to/cuda
```

**Installation**:
```shell
# Option 1: Add to PATH
export PATH=$PATH:/path/to/gcm/health_checks/cuda

# Option 2: Copy to system binary directory
sudo cp cudaMemTest /usr/local/bin/

# Option 3: Specify path explicitly when running check
health_checks -memtest --memtest-bin /path/to/cudaMemTest ...
```

### Binary Interface

The `cudaMemTest` binary accepts:
- `--device=<id>` - GPU device ID to test (required)
- `--alloc_mem_gb=<size>` - Memory allocation size in GB (default: 1GB)
- `--help` or `-?` - Display usage information

**Exit Codes**:
- `0` - Memory test passed successfully
- `1` - Test failed (allocation failure, memset failure, or CUDA error)

**Example Usage**:
```shell
# Test 8GB on GPU 0
./cudaMemTest --device=0 --alloc_mem_gb=8

# Output on success:
# free mem 85899345920 total mem 85899345920
# alloc 8
# CUDA memory test PASSED
```

## Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--size` | Integer | 4 GB | Memory allocation size in GB per GPU |
| `--memtest-bin` | Path | None | Path to `cudaMemTest` binary (uses PATH if not specified) |
| `--gpu-devices` / `-gpu` | Integer (multiple) | Auto-detect | GPU device IDs to test (can specify multiple). If it's called on prolog/epilog attempts reading `SLURM_JOB_GPUS`/`CUDA_VISIBLE_DEVICES` environment variables |
| `--timeout` | Integer | 300 | Command execution timeout in seconds |
| `--sink` | String | do_nothing | Telemetry sink destination |
| `--sink-opts` | Multiple | - | Sink-specific configuration |
| `--verbose-out` | Flag | False | Display detailed output |
| `--log-level` | Choice | INFO | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-folder` | String | `/var/log/fb-monitoring` | Log directory |
| `--heterogeneous-cluster-v1` | Flag | False | Enable heterogeneous cluster support |

## Validation Logic

### Concurrent Testing Process
1. **Thread pool creation**: One thread per GPU device
2. **Parallel execution**: All GPUs tested simultaneously
3. **Per-GPU test**:
   - Execute `cudaMemTest --device=<id> --alloc_mem_gb=<size>`
   - Wait for completion or timeout
   - Capture stdout, stderr, and return code
4. **Result aggregation**: Collect results as tests complete
5. **Exit code determination**: Use maximum exit code across all GPUs

### CUDA_VISIBLE_DEVICES Handling
The check temporarily unsets `CUDA_VISIBLE_DEVICES` during execution to prevent CUDA runtime from remapping device IDs:
- Device IDs from `SLURM_JOB_GPUS` (e.g., `2,3,5`) are already absolute physical IDs
- Unsetting ensures `cudaMemTest --device=2` tests physical GPU 2, not the CUDA-remapped device 0
- Prevents device ID confusion when SLURM has set `CUDA_VISIBLE_DEVICES`
- Restored automatically after test completion

## Exit Conditions

| Exit Code | Condition |
|-----------|-----------|
| **OK (0)** | Feature flag disabled (killswitch active) |
| **OK (0)** | All tests passed |
| **WARN (1)** | Test exception |
| **CRITICAL (2)** | Memory test failed |
| **UNKNOWN (3)** | No devices found |
| **UNKNOWN (3)** | Test not executed |

## Usage Examples

### Basic Memory Test
```shell
health_checks cuda memtest --sink stdout [CLUSTER] app
```
Uses `SLURM_JOB_GPUS` to auto-detect allocated GPUs and tests 4GB per GPU.

### Test Specific GPUs with Custom Size
```shell
health_checks cuda memtest \
  --size 16 \
  --gpu-devices 0 \
  --gpu-devices 1 \
  --gpu-devices 2 \
  --gpu-devices 3 \
  --sink stdout \
  [CLUSTER] \
  app
```
Tests GPUs 0-3 with 16GB allocation per GPU.

### Custom Binary Path with Extended Timeout
```shell
health_checks cuda memtest \
  --memtest-bin /opt/cuda/bin/cudaMemTest \
  --timeout 600 \
  --size 32 \
  --sink otel \
  --sink-opts "log_resource_attributes={'attr_1': 'value1'}" \
  [CLUSTER] \
  app
```
