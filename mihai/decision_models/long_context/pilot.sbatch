#!/usr/bin/env bash
# CPU preparation defaults; the GPU submission overrides partition, memory and time.
#SBATCH --job-name=glide-lengths
#SBATCH --account=cpsc4880
#SBATCH --partition=devel
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=00:30:00
#SBATCH --no-requeue
set -euo pipefail
project="${1:?Project root}"
source="${2:?Frozen pilot folder}"
stage="${3:?prepare or measure}"
[[ "$stage" == prepare || "$stage" == measure ]]
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
export XDG_CACHE_HOME="$project/cache/glide"
export TRITON_CACHE_DIR="$project/cache/glide/triton"
"$project/envs/monitor-glide-ab54df5a/bin/python" -B "$source/$stage.py" "$source/config.json"
