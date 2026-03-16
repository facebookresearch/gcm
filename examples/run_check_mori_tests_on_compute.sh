#!/bin/bash
# Submit a job to run GCM check_mori and killswitch tests on a SLURM compute node.
# Run this from the login node (no GPU needed for these unit tests).
#
# Usage (from login node):
#   cd /home/jenkins/gcm/examples && ./run_check_mori_tests_on_compute.sh
# To use another partition: PARTITION=your_partition ./run_check_mori_tests_on_compute.sh
#
# Output: gcm_check_mori_tests_<jobid>.out and .err in the directory where you ran the script.
# Check status: squeue -u $USER
# Tail output: tail -f gcm_check_mori_tests_<jobid>.out
# If cluster requires minimum runtime: sbatch -t 04:30:00 run_check_mori_tests_on_compute.sh

GCM_ROOT="${GCM_ROOT:-/home/jenkins/gcm}"
PARTITION="${PARTITION:-amd-rccl}"

sbatch \
  --job-name=gcm-check-mori-tests \
  --nodes=1 \
  --ntasks=1 \
  -t 00:05:00 \
  --mem=8192 \
  --partition="$PARTITION" \
  --output=gcm_check_mori_tests_%j.out \
  --error=gcm_check_mori_tests_%j.err \
  --wrap="
set -e
cd $GCM_ROOT
if [ -d \"$GCM_ROOT/.venv\" ]; then export PATH=\"$GCM_ROOT/.venv/bin:\$PATH\"; fi
pip install -e '.[dev]' -q 2>/dev/null || pip install -e . -q
echo '=== Host:' \$(hostname)
echo '=== Python:' \$(which python3) \$(python3 --version)
echo '=== Pytest: test_check_mori + test_killswitches ==='
python3 -m pytest gcm/tests/health_checks_tests/test_check_mori.py gcm/tests/health_checks_tests/test_killswitches.py -v
"
