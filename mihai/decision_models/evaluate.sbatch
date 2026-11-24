#!/usr/bin/env bash
# Defaults are for CPU preflight. GPU submission overrides partition/memory/time.
#SBATCH --job-name=glide-eval
#SBATCH --account=cpsc4880
#SBATCH --partition=devel
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --no-requeue
set -euo pipefail
script="${1:?Path to run_evaluation.py}"
stage="${2:?prepare or run}"
config="${3:?Path to evaluation configuration}"
project="${4:?Shared project directory}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
export XDG_CACHE_HOME="$project/cache/glide"
export TRITON_CACHE_DIR="$project/cache/glide/triton"
export OMP_NUM_THREADS=4
mkdir -p "$TRITON_CACHE_DIR"
if [[ "$stage" == run ]]; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
fi
"$project/envs/monitor-glide-ab54df5a/bin/python" -B "$script" "$stage" "$config"
