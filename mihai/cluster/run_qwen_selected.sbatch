#!/usr/bin/env bash
# H200 continuation: only the explicitly selected never-started/interrupted pairs.
# This only coordinates the repository's existing download/serve/rollout scripts.
set -euo pipefail

stage="${1:?Expected download or rollouts}"
expected_commit="${2:?Expected repository commit}"
tensor_parallel="${3:-1}"
rollout_workers="${4:-1}"
max_model_len="${5:-40960}"
yarn_factor="${6:-0}"
rollout_config="${7:-configs/rollouts.toml}"
expected_config_sha256="${8:-}"
source_snapshot="${9:-}"
expected_source_sha256="${10:-}"
selection="${11:?Expected selection path}"
selection_sha256="${12:?Expected selection hash}"
driver="${13:?Expected selected-pair driver}"
driver_sha256="${14:?Expected driver hash}"
[[ "$stage" == rollouts && "$tensor_parallel" == 1 && "$rollout_workers" == 8 ]] || exit 2
[[ "$(sha256sum "$selection" | cut -d " " -f 1)" == "$selection_sha256" ]] || exit 1
[[ "$(sha256sum "$driver" | cut -d " " -f 1)" == "$driver_sha256" ]] || exit 1
[[ "$tensor_parallel" =~ ^[1-9][0-9]*$ && "$rollout_workers" =~ ^[1-9][0-9]*$ ]] || exit 2
case "$max_model_len:$yarn_factor" in
    40960:0|65536:2|131072:4) ;;
    *) echo "Supported context/YaRN pairs: 40960/0, 65536/2, 131072/4" >&2; exit 2 ;;
esac
project=/nfs/roberts/project/cpsc4880/cpsc4880_mae73
repo="$project/monitor-similarity-experiment"
if [[ -n "$source_snapshot" ]]; then
    [[ "$source_snapshot" == "$project"/releases/qwen-* && "$expected_source_sha256" =~ ^[0-9a-f]{64}$ ]] || exit 2
    repo="$source_snapshot"
fi
research_python="$project/envs/monitor-research/bin/python"
serving_python="$project/envs/monitor-vllm/bin/python"
port=28473
subset_cache="$project/cache/qwen-h200-remaining-${SLURM_JOB_ID}"
server_pid=
worker_pids=()
status_file="$project/logs/qwen-${stage}-${SLURM_JOB_ID}.status"

export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
export HF_HOME="$project/cache/huggingface"
export VLLM_CACHE_ROOT="$project/cache/vllm"
export TORCH_HOME="$project/cache/torch"
export XDG_CACHE_HOME="$project/cache/xdg"
export CUDA_CACHE_PATH="$project/cache/cuda"
export OMP_NUM_THREADS=4
mkdir -p "$HF_HOME" "$VLLM_CACHE_ROOT" "$TORCH_HOME" "$XDG_CACHE_HOME" "$CUDA_CACHE_PATH"

share_outputs() {
    local path
    for path in "$project/models/qwen3-14b" "$project/cache/rollouts" \
                "$project/cache/followups" "$project/cache/entries" "$project/cache/manifests" "$subset_cache"; do
        if [[ -e "$path" ]]; then
            setfacl -R -m u:cpsc4880_ems264:rX,u:cpsc4880_jjj49:rX,u:cpsc4880_as4833:rX "$path"
        fi
    done
}

cleanup() {
    local code=$?
    trap - EXIT
    for worker_pid in "${worker_pids[@]}"; do
        kill -TERM "$worker_pid" 2>/dev/null || true
    done
    if [[ -n "$server_pid" ]]; then
        kill -TERM -- "-$server_pid" 2>/dev/null || true
    fi
    if ! share_outputs; then
        echo "Could not restore all teammate read permissions" >&2
        [[ "$code" != 0 ]] || code=1
    fi
    printf 'exit_code=%s finished_at=%s\n' "$code" "$(date -u +%FT%TZ)" >> "$status_file"
    exit "$code"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

cd "$repo"
if [[ -n "$source_snapshot" ]]; then
    # Verify the authorized, uncommitted fix as a frozen release before import.
    # Ordinary launches still require an unchanged reviewed Git checkout.
    "$research_python" - "$expected_source_sha256" "$expected_commit" <<'PY'
import hashlib, json, sys
from pathlib import Path
root = Path.cwd()
manifest_path = root / "source-manifest.json"
assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == sys.argv[1], "Source manifest changed"
manifest = json.loads(manifest_path.read_text())
assert manifest["base_commit"] == sys.argv[2], "Source base commit changed"
files = manifest["files"]
actual = {str(p.relative_to(root)) for p in root.rglob("*")
          if p.is_file() and p.relative_to(root).parts[0] not in ("models", "cache", ".runtime")
          and p != manifest_path}
assert actual == set(files), "Source file inventory changed"
for name, expected in files.items():
    path = root / name
    assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"Source changed: {name}"
print(f"Verified frozen source: {len(files)} files; manifest SHA256={sys.argv[1]}")
PY
else
    [[ "$(git rev-parse HEAD)" == "$expected_commit" ]] || { echo "Repository commit changed" >&2; exit 1; }
    git diff --quiet HEAD -- scripts monitor_experiment vendor configs prompts requirements*.txt
fi
exec 9>"$project/cache/qwen-pipeline.lock"
flock -n 9 || { echo "Another Qwen pipeline stage is active" >&2; exit 1; }
printf 'stage=%s job=%s node=%s commit=%s started_at=%s\n' \
    "$stage" "$SLURM_JOB_ID" "$(hostname)" "$expected_commit" "$(date -u +%FT%TZ)" | tee "$status_file"
printf 'source=%s source_manifest_sha256=%s\n' "$repo" "$expected_source_sha256" >> "$status_file"

case "$stage" in
    download)
        "$research_python" scripts/generate_rollouts.py --check-environments
        "$research_python" scripts/download_model.py
        ;;
    rollouts)
        # Freeze the selected configuration before the pilot or workers run.
        config_sha256=$(sha256sum "$rollout_config" | cut -d ' ' -f 1)
        if [[ -n "$expected_config_sha256" && "$config_sha256" != "$expected_config_sha256" ]]; then
            echo "Rollout configuration changed since submission" >&2; exit 1
        fi
        config_snapshot="$project/logs/qwen-config-${SLURM_JOB_ID}.toml"
        cp "$rollout_config" "$config_snapshot"
        [[ "$(sha256sum "$config_snapshot" | cut -d ' ' -f 1)" == "$config_sha256" ]] || exit 1
        "$research_python" - "$config_snapshot" "$max_model_len" <<'PY'
import sys, tomllib
from pathlib import Path
config = tomllib.loads(Path(sys.argv[1]).read_text())
for section in ("generation", "followup"):
    value = config[section]["max_tokens"]
    if not isinstance(value, int) or not 0 < value < int(sys.argv[2]):
        raise SystemExit(f"Invalid {section}.max_tokens for this context")
print(f"response_tokens={config['generation']['max_tokens']} followup_tokens={config['followup']['max_tokens']} request_timeout={config['generation']['timeout']}")
PY
        printf 'max_model_len=%s yarn_factor=%s config=%s config_sha256=%s\n' \
            "$max_model_len" "$yarn_factor" "$config_snapshot" "$config_sha256" >> "$status_file"
        nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
        "$research_python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 28473)); s.close()'
        server_log="$project/logs/qwen-server-${SLURM_JOB_ID}.log"
        server_args=(--port "$port" --tensor-parallel-size "$tensor_parallel" --max-model-len "$max_model_len")
        if [[ "$yarn_factor" != 0 ]]; then
            server_args+=(--yarn-factor "$yarn_factor")
        fi
        setsid "$serving_python" scripts/serve_model.py "${server_args[@]}" > "$server_log" 2>&1 &
        server_pid=$!
        ready=0
        for ((attempt=0; attempt<360; attempt++)); do
            if ! kill -0 "$server_pid" 2>/dev/null; then
                tail -n 100 "$server_log" >&2
                echo "Model server exited before readiness" >&2
                exit 1
            fi
            if curl --silent --fail --max-time 2 "http://127.0.0.1:$port/health" >/dev/null; then
                ready=1
                break
            fi
            sleep 5
        done
        [[ "$ready" == 1 ]] || { tail -n 100 "$server_log" >&2; echo "Server startup timed out" >&2; exit 1; }
        printf 'server_ready_at=%s\n' "$(date -u +%FT%TZ)" >> "$status_file"
        nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv > "$project/logs/qwen-gpu-${SLURM_JOB_ID}.csv"
        printf 'tensor_parallel=%s workers=%s selected_pairs=30 cache=%s\n' \
            "$tensor_parallel" "$rollout_workers" "$subset_cache" >> "$status_file"
        "$research_python" "$driver" --selection "$selection" --source "$repo" \
            --config "$config_snapshot" --cache "$subset_cache" --logs "$project/logs" \
            --job-id "$SLURM_JOB_ID" --base-url "http://127.0.0.1:$port/v1" --workers "$rollout_workers" &
        worker_pids=("$!")
        code=0
        wait "${worker_pids[0]}" || code=$?
        worker_pids=()
        [[ "$code" == 0 ]] || exit "$code"
        ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
