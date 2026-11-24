#!/usr/bin/env bash
# Run on the cluster; creates a separate environment, without changing Qwen.
set -euo pipefail
: "${PROJECT:?Set PROJECT to the shared cluster project directory}"
setup_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
bootstrap="${PYTHON312:-/apps/software/system/software/miniconda/24.11.3/bin/python}"
env_dir="$PROJECT/envs/monitor-glide-ab54df5a"
export PYTHONDONTWRITEBYTECODE=1
export HF_HOME="$PROJECT/cache/huggingface"
# Ordinary HTTPS avoids the Xet transfer stall observed on the cluster.
export HF_HUB_DISABLE_XET=1
export PIP_CACHE_DIR="$PROJECT/cache/pip-decision"
mkdir -p "$PROJECT/envs" "$HF_HOME" "$PIP_CACHE_DIR" "$PROJECT/logs"
exec 9>"$PROJECT/logs/setup-glide-ab54df5a.lock"
flock -n 9 || { echo 'Another GLiDE setup is running.' >&2; exit 1; }
"$bootstrap" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 required"'
if [[ ! -e "$env_dir" ]]; then
    "$bootstrap" -m venv "$env_dir"
fi
python="$env_dir/bin/python"
"$python" -m pip install 'huggingface_hub==1.33.0'
"$python" -B "$setup_dir/download_glide.py" "$PROJECT"
model_dir="$PROJECT/models/glide-9b-ab54df5a"
# The official requirements use CUDA 13.0 / NVIDIA driver 580+.
"$python" -m pip install --extra-index-url https://download.pytorch.org/whl/cu130 -r "$model_dir/requirements.txt"
"$python" -m pip check
"$python" -m pip freeze > "$env_dir/requirements-installed.txt"
echo "Installed environment: $env_dir"
echo 'GPU inference is NOT verified until smoke.sbatch passes on an allocated GPU.'
