#!/usr/bin/env bash
# Submit with absolute script/project arguments; no rollout data is read.
#SBATCH --job-name=glide-smoke
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_devel,gpu_rtx6000
#SBATCH --constraint=gpu:rtx_pro_6000_blackwell
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -euo pipefail
project="${1:?Shared project directory required}"
test_script="${2:?Absolute smoke.py path required}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1
export XDG_CACHE_HOME="$project/cache/glide"
export TRITON_CACHE_DIR="$project/cache/glide/triton"
mkdir -p "$TRITON_CACHE_DIR"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
driver=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
[[ "${driver%%.*}" -ge 580 ]] || { echo 'Pinned CUDA 13.0 environment requires driver 580+.' >&2; exit 1; }
"$project/envs/monitor-glide-ab54df5a/bin/python" -B "$test_script" glide \
    --model-dir "$project/models/glide-9b-ab54df5a"
# Run the readable examples after the installation check passes.
"$project/envs/monitor-glide-ab54df5a/bin/python" -B "$(dirname "$test_script")/demo_glide.py" \
    "$project/models/glide-9b-ab54df5a"
