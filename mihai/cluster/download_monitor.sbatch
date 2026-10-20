#!/usr/bin/env bash
# Download a registered monitor's weights on a CPU node (compute nodes have internet; the login node should not carry a 65 GB transfer).
# See docs/system/cluster.md B4. Submit, for example:
#   MONITOR=qwen3-32b sbatch --account=cpsc4880 --partition=day --cpus-per-task=4 --mem=16G --time=04:00:00 \
#       --output=$ME/logs/download-%j.out mihai/cluster/download_monitor.sbatch
# Environment: MONITOR (required); OUT (default $ME/models/$MONITOR); REVISION (optional override of the registry's pin).
set -euo pipefail
ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
FRAMEWORK="${FRAMEWORK:-$ME/monitor-framework}"
: "${MONITOR:?set MONITOR to a registry name}"
OUT="${OUT:-$ME/models/$MONITOR}"
PY="$ME/envs/monitor-analysis/bin/python"
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HOME="$ME/cache/huggingface"
mkdir -p "$ME/logs" "$HF_HOME" "$OUT"
echo "job=${SLURM_JOB_ID:-local} node=$(hostname) started=$(date -u +%FT%TZ) monitor=$MONITOR out=$OUT"
df -h "$ME" | tail -1
args=(--output-dir "$OUT")
[[ -n "${REVISION:-}" ]] && args+=(--revision "$REVISION")
"$PY" "$FRAMEWORK/scripts/download_monitor.py" "$MONITOR" "${args[@]}"
"$PY" "$FRAMEWORK/scripts/download_monitor.py" "$MONITOR" --output-dir "$OUT" --verify-only
echo "finished=$(date -u +%FT%TZ)"
