#!/usr/bin/env bash
# Serve ONE registered monitor on this job's GPU(s) and run an experiment file against it. One model per server, so one monitor per job.
# See docs/system/cluster.md. Submit, for example:
#   MONITOR=qwen3-32b EXPERIMENT=configs/experiments/baseline.toml MODEL_DIR=$ME/models/qwen3-32b \
#   sbatch --gres=gpu:h200:1 --cpus-per-task=6 --mem=96G --time=06:00:00 mihai/cluster/run_monitor.sbatch
# Environment: MONITOR, EXPERIMENT, MODEL_DIR (required); TP (tensor parallel, 1); GPU_LABEL (for GPU-hour accounting, "H200:1");
#              EXTRA_ARGS (more run_experiment.py arguments, e.g. "--set options.samples=2"); PORT;
#              SCORE (1 = compute metrics after the run, the default; use SCORE=0 for the format-only pilot, which must not read labels).
set -euo pipefail

ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
FRAMEWORK="${FRAMEWORK:-$ME/monitor-framework}"
: "${MONITOR:?set MONITOR to a registry name}" "${EXPERIMENT:?set EXPERIMENT to an experiment file}" "${MODEL_DIR:?set MODEL_DIR}"
TP="${TP:-1}"
GPU_LABEL="${GPU_LABEL:-H200:$TP}"
PORT="${PORT:-28474}"
EXTRA_ARGS="${EXTRA_ARGS:-}"
RUNS_DIR="${RUNS_DIR:-$ME/runs}"
SCORE="${SCORE:-1}"
score_flag=()
[[ "$SCORE" == 1 ]] && score_flag=(--score)
SERVING_PY="${SERVING_PY:-/nfs/roberts/project/cpsc4880/cpsc4880_mae73/envs/monitor-vllm/bin/python}"
ANALYSIS_PY="${ANALYSIS_PY:-$ME/envs/monitor-analysis/bin/python}"
registry_args=()
[[ -n "${REGISTRY_DIR:-}" ]] && registry_args=(--registry-dir "$REGISTRY_DIR")
eager_args=()
case "${ENFORCE_EAGER:-0}" in
    0) ;;
    1) eager_args=(--enforce-eager) ;;
    *) echo 'ENFORCE_EAGER must be 0 or 1' >&2; exit 1 ;;
esac
JOB="${SLURM_JOB_ID:-local}"
STATUS="$ME/logs/monitor-$MONITOR-$JOB.status"
server_pid=

export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export HF_HOME="$ME/cache/huggingface" VLLM_CACHE_ROOT="$ME/cache/vllm" TORCH_HOME="$ME/cache/torch" XDG_CACHE_HOME="$ME/cache/xdg"
mkdir -p "$ME/logs" "$HF_HOME" "$VLLM_CACHE_ROOT" "$TORCH_HOME" "$XDG_CACHE_HOME"

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

cd "$FRAMEWORK"
if [[ -n "${GEMMA_ENV_LOCK:-}" ]]; then
    exec 8> "$GEMMA_ENV_LOCK"
    flock -s -n 8 || { echo 'The Gemma environment is being repaired; retry after repair completes' >&2; exit 1; }
fi
# A run directory has one manifest and JSONL streams. Separate processes must
# not append to it simultaneously, even if another submitter bypassed the queue.
run_name=$("$ANALYSIS_PY" -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["name"])' "$EXPERIMENT")
[[ "$run_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || { echo "Unsafe experiment name: $run_name" >&2; exit 1; }
mkdir -p "$RUNS_DIR/$run_name"
exec 9> "$RUNS_DIR/$run_name/.monitor-job.lock"
flock -n 9 || { echo "Another job is writing run $run_name" >&2; exit 1; }
if [[ -n "${SEED_BASELINE:-}" ]]; then
    "$ANALYSIS_PY" scripts/seed_monitor_run.py --source "$SEED_BASELINE" --target "$RUNS_DIR/$run_name" \
        --monitor "$MONITOR" --experiment "$EXPERIMENT" "${registry_args[@]}"
fi
printf 'job=%s monitor=%s experiment=%s node=%s started_at=%s\n' "$JOB" "$MONITOR" "$EXPERIMENT" "$(hostname)" "$(date -u +%FT%TZ)" | tee -a "$STATUS"
printf 'framework=%s results=%s analysis_python=%s serving_python=%s\n' "$FRAMEWORK" "$RUNS_DIR/$run_name" "$ANALYSIS_PY" "$SERVING_PY" | tee -a "$STATUS"
printf 'enforce_eager=%s cuda_launch_blocking=%s\n' "${ENFORCE_EAGER:-0}" "${CUDA_LAUNCH_BLOCKING:-0}" | tee -a "$STATUS"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | tee -a "$STATUS"
if [[ "$MONITOR" == gemma4-* ]]; then
    source "$FRAMEWORK/mihai/cluster/cuda_toolkit.sh"
    configure_monitor_cuda
    printf 'torch_cuda=%s nvcc_version=%s cuda_home=%s cuda_module=%s loaded_modules=%s ninja=%s ninja_version=%s\n' \
        "$MONITOR_TORCH_CUDA" "$MONITOR_NVCC_VERSION" "$CUDA_HOME" "$MONITOR_CUDA_MODULE" "${LOADEDMODULES:-}" \
        "$MONITOR_NINJA_PATH" "$MONITOR_NINJA_VERSION" | tee -a "$STATUS"
fi
# A port is "taken" only if something is listening. Closed connections of a previous server linger in TIME_WAIT for a minute, so bind with SO_REUSEADDR as the server does.
"$ANALYSIS_PY" -c 'import socket,sys; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("127.0.0.1", int(sys.argv[1]))); s.close()' "$PORT"

server_log="$ME/logs/monitor-server-$MONITOR-$JOB.log"
setsid "$SERVING_PY" scripts/serve_monitor.py --monitor "$MONITOR" --model-dir "$MODEL_DIR" --port "$PORT" \
    --tensor-parallel-size "$TP" --manifest "$ME/logs/serving-$MONITOR-$JOB.json" "${registry_args[@]}" "${eager_args[@]}" > "$server_log" 2>&1 &
server_pid=$!
ready=0
for ((attempt = 0; attempt < 720; attempt++)); do   # large models take a while to load: up to an hour
    kill -0 "$server_pid" 2>/dev/null || { tail -n 100 "$server_log" >&2; echo "Monitor server exited before readiness" >&2; exit 1; }
    if curl --silent --fail --max-time 2 "http://127.0.0.1:$PORT/health" > /dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { tail -n 100 "$server_log" >&2; echo "Server startup timed out" >&2; exit 1; }
printf 'server_ready_at=%s\n' "$(date -u +%FT%TZ)" >> "$STATUS"

# shellcheck disable=SC2086   # EXTRA_ARGS is deliberately word-split
"$ANALYSIS_PY" scripts/run_experiment.py "$EXPERIMENT" --monitor "$MONITOR" --base-url "http://127.0.0.1:$PORT/v1" \
    --out "$RUNS_DIR" --gpu "$GPU_LABEL" --job-id "$JOB" "${registry_args[@]}" "${score_flag[@]}" $EXTRA_ARGS 2>&1 | tee -a "$STATUS"
# Always write the label-free summary (validity, reply lengths, plan sizes, latency): it is what the pilot is judged on.
"$ANALYSIS_PY" scripts/pilot_summary.py "$RUNS_DIR/$run_name" --monitor "$MONITOR" --json "$RUNS_DIR/$run_name/pilot-summary-$MONITOR.json" 2>&1 | tee -a "$STATUS"
