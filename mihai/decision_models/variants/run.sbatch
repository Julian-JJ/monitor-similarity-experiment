#!/usr/bin/env bash
# Resource flags are supplied at submission: prepare=CPU, qwen=H200, glide=Blackwell.
#SBATCH --account=cpsc4880
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --no-requeue
set -euo pipefail
stage="${1:?stage}"
config="${2:?absolute config path}"
project="${3:?project directory}"
package="$(cd -- "$(dirname -- "$config")" && pwd)"
analysis="$project/envs/monitor-research/bin/python"
glide="$project/envs/monitor-glide-ab54df5a/bin/python"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONFAULTHANDLER=1
export HF_HUB_OFFLINE=1 OMP_NUM_THREADS=4
export XDG_CACHE_HOME="$project/cache/glide" TRITON_CACHE_DIR="$project/cache/glide/triton"
extra=()
if [[ "${4:-}" == smoke ]]; then extra=(--smoke); fi
server_pid=
status="$project/logs/decision-variants-${stage}-${SLURM_JOB_ID}.status"
cleanup() {
    code=$?
    trap - EXIT
    if [[ -n "$server_pid" ]]; then kill -TERM -- "-$server_pid" 2>/dev/null || true; fi
    printf 'exit_code=%s finished_utc=%s\n' "$code" "$(date -u +%FT%TZ)" >> "$status"
    exit "$code"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
printf 'stage=%s job=%s started_utc=%s\n' "$stage" "$SLURM_JOB_ID" "$(date -u +%FT%TZ)" > "$status"
if [[ "$stage" == qwen ]]; then
    # The GLiDE environment also has the tokenizer needed by the Qwen client.
    # Check it before reserving time to load the model server.
    "$glide" -B -c 'from tokenizers import Tokenizer'
    framework="$($analysis -c 'import json,sys; print(json.load(open(sys.argv[1]))["framework_source"])' "$config")"
    model="$($analysis -c 'import json,sys; print(json.load(open(sys.argv[1]))["qwen_model_dir"])' "$config")"
    port=28474
    "$analysis" -c 'import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",28474)); s.close()'
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
    # setsid gives this server its own process group; cleanup stops only that group.
    setsid "$project/envs/monitor-vllm/bin/python" -B "$framework/scripts/serve_monitor.py" \
        --monitor qwen3-32b --model-dir "$model" --port "$port" --tensor-parallel-size 1 \
        --manifest "$project/logs/decision-variants-serving-${SLURM_JOB_ID}.json" \
        > "$project/logs/decision-variants-server-${SLURM_JOB_ID}.log" 2>&1 &
    server_pid=$!
    ready=0
    for ((i=0;i<720;i++)); do
        kill -0 "$server_pid" 2>/dev/null || { echo 'Server failed before readiness'; exit 1; }
        if curl --silent --fail --max-time 2 "http://127.0.0.1:$port/health" >/dev/null; then ready=1; break; fi
        sleep 5
    done
    [[ "$ready" == 1 ]] || { echo 'Server readiness timeout'; exit 1; }
    "$glide" -B "$package/run_variants.py" qwen "$config" --base-url "http://127.0.0.1:$port/v1" "${extra[@]}"
elif [[ "$stage" == score ]]; then
    "$analysis" -B "$package/run_variants.py" score "$config"
else
    if [[ "$stage" == glide-* ]]; then nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv; fi
    "$glide" -B "$package/run_variants.py" "$stage" "$config" "${extra[@]}"
fi
