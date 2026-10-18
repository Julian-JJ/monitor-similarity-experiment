#!/usr/bin/env bash
set -euo pipefail
release=${1:?Expected immutable release directory}
expected_manifest=${2:?Expected release manifest SHA256}
project=/nfs/roberts/project/cpsc4880/cpsc4880_mae73
experiment="$project/test_rollouts_2"
output="$experiment/runs/$SLURM_JOB_ID"
research="$project/envs/monitor-research/bin/python"
serving="$project/envs/monitor-vllm/bin/python"
server_pid=
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=4
export HF_HOME="$project/cache/huggingface" VLLM_CACHE_ROOT="$project/cache/vllm"
export TORCH_HOME="$project/cache/torch" XDG_CACHE_HOME="$project/cache/xdg" CUDA_CACHE_PATH="$project/cache/cuda"
mkdir -p "$output"
cleanup() {
    code=$?
    trap - EXIT
    if [[ -n "$server_pid" ]]; then
        kill -TERM -- "-$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    printf 'exit_code=%s finished_at=%s\n' "$code" "$(date -u +%FT%TZ)" >> "$output/status.txt"
    setfacl -R -m u:cpsc4880_ems264:rX,u:cpsc4880_jjj49:rX,u:cpsc4880_as4833:rX "$output" || true
    exit "$code"
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
exec 9>"$project/cache/qwen-pipeline.lock"
flock -n 9 || { echo 'Another Qwen campaign is active'; exit 1; }
"$research" -B - "$release" "$expected_manifest" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);p=r/'release-manifest.json'
assert hashlib.sha256(p.read_bytes()).hexdigest()==sys.argv[2]
m=json.loads(p.read_text())
assert {str(x.relative_to(r)) for x in r.rglob('*') if x.is_file() and x!=p}==set(m['files'])
for name,expected in m['files'].items():
 assert not (r/name).is_symlink()
 assert hashlib.sha256((r/name).read_bytes()).hexdigest()==expected,name
print('Complete release inventory verified:',len(m['files']))
PY
nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv > "$output/gpu.csv"
grep -q H200 "$output/gpu.csv"
printf 'job=%s started_at=%s node=%s\n' "$SLURM_JOB_ID" "$(date -u +%FT%TZ)" "$(hostname)" > "$output/status.txt"
setsid "$serving" -B "$release/serve.py" --model-dir "$project/models/qwen3-14b" \
    --config "$release/config.json" --output "$output/serving-manifest.json" > "$output/server.log" 2>&1 &
server_pid=$!
ready=0
for ((i=0; i<180; i++)); do
    kill -0 "$server_pid" 2>/dev/null || { echo 'Server exited before readiness'; exit 1; }
    if curl --silent --fail --max-time 2 http://127.0.0.1:28475/health >/dev/null; then ready=1; break; fi
    sleep 5
done
[[ "$ready" == 1 ]] || { echo 'Server readiness timeout'; exit 1; }
"$research" -B "$release/run.py" --release "$release" --output "$output" \
    --job-id "$SLURM_JOB_ID" --model-dir "$project/models/qwen3-14b" > "$output/driver.log" 2>&1
