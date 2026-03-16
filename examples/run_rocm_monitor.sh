#!/bin/bash
#SBATCH --job-name=gcm-rocm-monitor
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --gres=gpu:1
#SBATCH -t 00:05:00
#SBATCH --mem=8192
#SBATCH --partition=amd-rccl
#SBATCH --output=gcm_rocm_monitor_%j.out
#SBATCH --error=gcm_rocm_monitor_%j.err
#
# Run gcm rocm_monitor on a SLURM compute node (amd-smi/rocm-smi are only on compute nodes).
# Usage:
#   sbatch run_rocm_monitor.sh
#   sbatch -t 04:30:00 run_rocm_monitor.sh   # if cluster requires minimum runtime
#
# Optional: run on a specific node: sbatch --nodelist=useocpm2m-097-038 run_rocm_monitor.sh
#
# If job shows (launch failed requeued held): run "scontrol release JOBID" to retry,
# or "scontrol show job JOBID" and check ReqTRES (e.g. mem should be 8192M, not 2000000M).

set -e
cd /home/jenkins/gcm
export PATH="/home/jenkins/gcm/.venv/bin:$PATH"
pip install --no-deps -e . -q
echo '=== gcm rocm_monitor --sink=stdout --once ==='
gcm rocm_monitor --sink=stdout --once
