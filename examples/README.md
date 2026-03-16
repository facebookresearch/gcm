# GCM Examples (AMD GPU / ROCm / MORI)

Example scripts for running GCM monitoring and health checks on **AMD GPU clusters** with SLURM. These scripts assume a partition such as `amd-rccl` and that compute nodes have `amd-smi` or `rocm-smi` on PATH.

**Requirements**: SLURM cluster with AMD GPU partition; GCM installed (e.g. `pip install -e .` in repo root). If your cluster requires an explicit runtime limit, submit with `sbatch -t 04:30:00 <script>`.

## Scripts

| Script | Purpose |
|--------|---------|
| **run_rocm_monitor.sh** | One-shot AMD GPU metrics: runs `gcm rocm_monitor --once` on a single compute node. Output: `gcm_rocm_monitor_<jobid>.out` / `.err`. |
| **test_gcm.sh** | Detects environment: on a compute node runs `gcm rocm_monitor --once`; on login node runs `gcm slurm_monitor --once`. Output: `gcm_test_<jobid>.out` / `.err`. |
| **run_check_mori_tests_on_compute.sh** | Submits a job to run GCM unit tests for **check_mori** and **killswitches** on a compute node (pytest). Output: `gcm_check_mori_tests_<jobid>.out` / `.err`. |

## Usage

From the GCM repo root:

```bash
# ROCm monitor (one node, one snapshot)
sbatch examples/run_rocm_monitor.sh
# Optional: specific node or longer time
# sbatch -t 04:30:00 examples/run_rocm_monitor.sh
# sbatch --nodelist=useocpm2m-097-038 examples/run_rocm_monitor.sh

# GCM test (rocm_monitor or slurm_monitor depending on node)
sbatch examples/test_gcm.sh

# MORI and killswitch tests (pytest on compute node)
cd examples && ./run_check_mori_tests_on_compute.sh
# Or with partition override: PARTITION=amd-rccl ./run_check_mori_tests_on_compute.sh
```

Check job status and output:

```bash
squeue -u $USER
tail -f gcm_rocm_monitor_<jobid>.out
```

## Cluster-specific notes

- **Runtime**: Some clusters require `-t` (e.g. `-t 04:30:00`). Use `sbatch -t 04:30:00 examples/run_rocm_monitor.sh` if submission fails with "runtime limit is required".
- **Memory**: Scripts request `--mem=8192` (8 GB) to avoid default 2 TB and launch failures.
- **Paths**: Scripts use `/home/jenkins/gcm` and `.venv` by default; set `GCM_ROOT` or edit the script for your path.
