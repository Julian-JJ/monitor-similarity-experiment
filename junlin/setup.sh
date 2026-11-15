#!/usr/bin/env bash
# Prepare cluster environments and save settings; no model weights or Slurm jobs.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
setup_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$setup_root/.env.cluster" ]]; then
    source "$setup_root/.env.cluster"
fi
if [[ "${1:-}" == -h || "${1:-}" == --help ]]; then
    cat <<'HELP'
Usage: bash junlin/setup.sh [--install | --check | --status | --repair-gemma] [options]

  --install                Create/repair analysis and Gemma serving environments.
  --check                  Read-only verification; no installs, downloads or writes.
  --status                 Report job exits, progress and scoring for the new batch.
  --repair-gemma           Repair the native TorchAudio wheel without upgrading Torch/vLLM.
  --project-dir DIR        Your writable project directory (default: cluster account).
  --shared-dir DIR         Existing shared data/Qwen environment (default: cpsc4880_mae73).
  --original-rollouts DIR   Original collection directory containing manifest.json.
  --control-rollouts DIR    Main-task-only collection directory containing manifest.json.

Without a mode flag, reuse and verify existing environments and save settings.
The submitter automatically reads the generated, Git-ignored .env.cluster after login.
Use a CPU allocation for --install. No model weights are downloaded or jobs submitted.
SYSTEM_PYTHON, ANALYSIS_PY, GEMMA_SERVING_PY and SERVING_PY can override Python paths.
HELP
    exit 0
fi
if [[ -n "${SYSTEM_PYTHON:-}" ]]; then
    setup_candidates=("$SYSTEM_PYTHON")
else
    setup_candidates=(python3.12 /apps/software/system/software/miniconda/24.11.3/bin/python python3)
fi
for setup_python in "${setup_candidates[@]}"; do
    if command -v "$setup_python" >/dev/null 2>&1 &&
        "$setup_python" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
        exec "$setup_python" "$setup_root/junlin/setup_cluster_env.py" "$@"
    fi
done
echo 'ERROR: Python 3.11+ is required. Set SYSTEM_PYTHON to its executable.' >&2
exit 1
