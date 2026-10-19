#!/usr/bin/env bash
# Generate the main_only control rollouts: serve Qwen3-14B on ONE GPU, run the cached batch's actor settings, no side objective.
# Derived from run_qwen.sbatch. Differences: every path is a variable; all writes go under $ME; the teammate's directory is read-only;
# the variant is main_only; each (task, sample) runs in its own process (scripts/run_pairs.py). See docs/system/cluster.md.
#
# Submit (partition/account/time are cluster specifics, not set here):
#   sbatch --gres=gpu:h200:1 --cpus-per-task=8 --mem=96G --time=06:00:00 [--partition=... --account=...] \
#          mihai/cluster/run_controls.sbatch
# Environment (all optional): FIRST_SAMPLE (default 0), SAMPLES_PER_TASK (12), PARALLEL (8), PORT (28473).
set -euo pipefail

ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
SHARED="${SHARED:-/nfs/roberts/project/cpsc4880/cpsc4880_mae73}"
CHECKOUT="${CHECKOUT:-$ME/monitor-similarity-experiment}"
FRAMEWORK="${FRAMEWORK:-$ME/monitor-framework}"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-5dc0417}"
FIRST_SAMPLE="${FIRST_SAMPLE:-0}"
SAMPLES_PER_TASK="${SAMPLES_PER_TASK:-12}"
PARALLEL="${PARALLEL:-8}"
PORT="${PORT:-28473}"
MAX_MODEL_LEN=131072   # the cached batch's serving: 131,072 tokens with YaRN factor 4, one GPU
YARN_FACTOR=4
RESEARCH_PY="$SHARED/envs/monitor-research/bin/python"
SERVING_PY="$SHARED/envs/monitor-vllm/bin/python"
CONFIG="$ME/configs/rollouts-main-only.toml"
JOB="${SLURM_JOB_ID:-local}"
STATUS="$ME/logs/controls-$JOB.status"
server_pid=

export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export HF_HOME="$ME/cache/huggingface" VLLM_CACHE_ROOT="$ME/cache/vllm" TORCH_HOME="$ME/cache/torch"
export XDG_CACHE_HOME="$ME/cache/xdg" CUDA_CACHE_PATH="$ME/cache/cuda"
mkdir -p "$ME/logs" "$HF_HOME" "$VLLM_CACHE_ROOT" "$TORCH_HOME" "$XDG_CACHE_HOME" "$CUDA_CACHE_PATH"

cleanup() {
    local code=$?
    trap - EXIT
    [[ -n "$server_pid" ]] && kill -TERM -- "-$server_pid" 2>/dev/null || true
    printf 'exit_code=%s finished_at=%s\n' "$code" "$(date -u +%FT%TZ)" >> "$STATUS"
    exit "$code"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

cd "$CHECKOUT"
# 1. The code that generates must be the code that generated the cached rollouts: same commit, unmodified, same implementation hash.
"$RESEARCH_PY" "$FRAMEWORK/scripts/prepare_controls.py" verify-checkout --checkout "$CHECKOUT" --commit "$EXPECTED_COMMIT" \
    --manifest "$SHARED/rollouts_original_clean/manifest.json" | tee -a "$STATUS"
# 2. Only one pipeline stage at a time, as in the original.
exec 9>"$ME/cache/controls-pipeline.lock"
flock -n 9 || { echo "Another controls job is active" >&2; exit 1; }
printf 'job=%s node=%s commit=%s config_sha256=%s started_at=%s\n' "$JOB" "$(hostname)" "$EXPECTED_COMMIT" \
    "$(sha256sum "$CONFIG" | cut -d ' ' -f 1)" "$(date -u +%FT%TZ)" | tee -a "$STATUS"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee -a "$STATUS"
"$RESEARCH_PY" -c 'import socket,sys; s=socket.socket(); s.bind(("127.0.0.1", int(sys.argv[1]))); s.close()' "$PORT"

# 3. Serve the actor exactly as the cached batch was served (the checkout's own serve_model.py).
server_log="$ME/logs/controls-server-$JOB.log"
setsid "$SERVING_PY" scripts/serve_model.py --model-dir "$ME/models/qwen3-14b" --port "$PORT" --tensor-parallel-size 1 \
    --max-model-len "$MAX_MODEL_LEN" --yarn-factor "$YARN_FACTOR" > "$server_log" 2>&1 &
server_pid=$!
ready=0
for ((attempt = 0; attempt < 360; attempt++)); do
    kill -0 "$server_pid" 2>/dev/null || { tail -n 100 "$server_log" >&2; echo "Model server exited before readiness" >&2; exit 1; }
    if curl --silent --fail --max-time 2 "http://127.0.0.1:$PORT/health" > /dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { tail -n 100 "$server_log" >&2; echo "Server startup timed out" >&2; exit 1; }
printf 'server_ready_at=%s\n' "$(date -u +%FT%TZ)" >> "$STATUS"

# 4. One process per (task, sample), PARALLEL at a time (the cached batch used 8 clients). The generator stops its whole process at the first execution
#    failure, so block-sized workers lose every remaining sample of a block when one fails; a pair per process loses only the failed sample.
#    Samples already complete in the cache (under any serving identity) are skipped. See scripts/run_pairs.py.
"$RESEARCH_PY" "$FRAMEWORK/scripts/run_pairs.py" --checkout "$CHECKOUT" --python "$RESEARCH_PY" --config "$CONFIG" \
    --base-url "http://127.0.0.1:$PORT/v1" --cache-dir "$ME/cache" --log-dir "$ME/logs/controls-pairs-$JOB" \
    --samples "$SAMPLES_PER_TASK" --first-sample "$FIRST_SAMPLE" --parallel "$PARALLEL" 2>&1 | tee -a "$STATUS"
printf 'complete_actor_entries=%s\n' "$(ls "$ME/cache/entries" | wc -l)" | tee -a "$STATUS"
