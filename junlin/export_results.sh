#!/usr/bin/env bash
# CPU-only, read-only source-run audit. No installs, inference or submissions.
set -euo pipefail
export_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$export_root/.env.cluster" ]]; then
    source "$export_root/.env.cluster"
fi
: "${ME:?Run bash junlin/setup.sh once to save the cluster project directory}"
export_python="${ANALYSIS_PY:-$ME/envs/monitor-analysis/bin/python}"
exec "$export_python" "$export_root/junlin/compile_results.py" --export --project-dir "$ME" "$@"
