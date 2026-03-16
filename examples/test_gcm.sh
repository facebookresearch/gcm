#!/bin/bash
#SBATCH --job-name=gcm-test
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --gres=gpu:1
#SBATCH -t 00:05:00
#SBATCH --mem=8192
#SBATCH --output=gcm_test_%j.out
#SBATCH --error=gcm_test_%j.err
# Optional: run on a specific node (e.g. where amd-smi/rocm-smi exist)
# sbatch --nodelist=useocpm2m-097-038 test_gcm.sh
# #SBATCH --nodelist=useocpm2m-097-038

# Use your refactored gcm
export PATH="/home/jenkins/gcm/.venv/bin:$PATH"  # or activate your venv
cd /home/jenkins/gcm
pip install --no-deps -e . -q

# On login node (no AMD tools): slurm_monitor only. On compute node: rocm_monitor.
if command -v amd-smi &>/dev/null || command -v rocm-smi &>/dev/null; then
  gcm rocm_monitor --sink=stdout --once
else
  gcm slurm_monitor --sink=stdout --once
fi