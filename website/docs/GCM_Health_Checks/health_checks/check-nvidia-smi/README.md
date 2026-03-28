# check-nvidia-smi

Comprehensive GPU health validation using NVIDIA's NVML (NVIDIA Management Library) API for GPU hardware state, memory integrity, thermal status, and process occupancy.

## Available Health Checks

| Check | Purpose | Key Feature |
|-------|---------|-------------|
| [clock_freq](./clock_freq.md) | Clock frequency validation | Ensure GPU/memory clocks meet minimums |
| [clock_policy](./clock_policy.md) | Clock policy drift detection | Validate expected clocks with WARN/CRITICAL drift thresholds |
| [ecc_corrected_volatile_total](./ecc_corrected_volatile_total.md) | Corrected ECC errors | Monitor corrected error accumulation |
| [ecc_uncorrected_volatile_total](./ecc_uncorrected_volatile_total.md) | Uncorrected ECC errors | Validate uncorrected error counts |
| [gpu_mem_usage](./gpu_mem_usage.md) | Memory usage check | Verify GPU memory usage below limit |
| [gpu_num](./gpu_num.md) | GPU count validation | Verify expected number of GPUs detected |
| [gpu_retired_pages](./gpu_retired_pages.md) | Retired pages tracking | Monitor ECC-retired memory pages |
| [gpu_temperature](./gpu_temperature.md) | Thermal monitoring | Validate GPU temperatures below threshold |
| [row_remap_failed](./row_remap_failed.md) | Failed row remaps | Detect failed row remap operations |
| [row_remap_pending](./row_remap_pending.md) | Pending row remaps | Ensure no pending row remaps |
| [row_remap](./row_remap.md) | Row remapping status | Check for pending/failed row remaps |
| [running_procs_and_kill](./running_procs_and_kill.md) | Process cleanup | Retry logic with optional force-kill capability |
| [running_procs](./running_procs.md) | Process occupancy check | Detect processes using GPUs |
| [vbios_mismatch](./vbios_mismatch.md) | VBIOS consistency | Verify consistent VBIOS across GPUs |

## Quick Start

```shell
# GPU count check
health_checks check-nvidia-smi --check gpu_num --gpu_num 8 [CLUSTER] app

# Multiple checks
health_checks check-nvidia-smi --check gpu_num --check clock_freq --check running_procs [CLUSTER] app

# Temperature validation
health_checks check-nvidia-smi --check gpu_temperature --gpu_temperature_threshold 85 [CLUSTER] app
```
