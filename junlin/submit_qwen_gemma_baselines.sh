#!/usr/bin/env bash
# Submit the remaining size/family baselines on Bouchet; never runs inference on the login node.
set -euo pipefail
submission_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Restore verified cluster defaults after a new login; explicit environment overrides win.
if [[ -f "$submission_root/.env.cluster" ]]; then
    source "$submission_root/.env.cluster"
fi

usage() {
    cat <<'HELP'
Usage: bash junlin/submit_qwen_gemma_baselines.sh [--dry-run] [--parallel] [--repair-gemma] [--diagnostic] [--eager] [MODEL ...]

Default models: qwen3-1.7b qwen3-4b gemma4-e2b gemma4-e4b gemma4-12b gemma4-31b
Optional model: qwen3-30b-a3b

Each model gets a CPU preparation job (download/reuse weights, pin a private registry)
and an H200 monitor job dependent on successful preparation. GPU jobs run sequentially
and append to runs/baseline, retaining completed work. --dry-run prints commands only.
GPU jobs request 6 CPUs per GPU to match the cluster allocation limit.
--diagnostic runs a small Qwen3-1.7B job with eager execution and synchronous
CUDA errors in a separate run directory. --eager disables CUDA graphs for normal jobs.
--parallel gives each model its own run directory/port and removes GPU chaining.
--repair-gemma adds one CPU native-library repair prerequisite for all Gemma jobs.
For the five unfinished models use: bash junlin/retry.sh

Environment overrides:
  ME, FRAMEWORK, MODELS_DIR, ANALYSIS_PY, SERVING_PY, GEMMA_SERVING_PY, SUBMIT_PY
  ACCOUNT=cpsc4880 CPU_PARTITION=day GPU_PARTITION=gpu_h200
  CPU_TIME=04:00:00 GPU_TIME=08:00:00 GPU_COUNT=1 GPU_MEM=96G
  DEPENDENCY_JOB_ID=<existing monitor job> (serialize after an already queued run)

GEMMA_SERVING_PY is an optional path to the Python executable in an existing
environment supporting Gemma 4 and the gemma4 reasoning parser. Setting it does
not create/install an environment. It defaults to SERVING_PY if unset; use one
environment for both families if that environment supports both.
Sync this branch and prepare the two rollout collections and reference tokenizer first.
Real submissions check that vLLM is installed in every selected serving Python
before queuing any jobs. --dry-run does not require serving environments.
Run bash junlin/setup.sh --install once to prepare and save defaults.
The submitter automatically restores .env.cluster after a new login.
HELP
}

dry_run=0
diagnostic=0
enforce_eager=0
parallel=0
repair_gemma=0
monitors=()
while (($#)); do
    case "$1" in
        --dry-run) dry_run=1 ;;
        --diagnostic) diagnostic=1 ;;
        --eager) enforce_eager=1 ;;
        --parallel) parallel=1 ;;
        --repair-gemma) repair_gemma=1 ;;
        -h|--help) usage; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
        *) monitors+=("$1") ;;
    esac
    shift
done
if ((${#monitors[@]} == 0)); then
    if [[ "$diagnostic" == 1 ]]; then
        monitors=(qwen3-1.7b)
    else
        monitors=(qwen3-1.7b qwen3-4b gemma4-e2b gemma4-e4b gemma4-12b gemma4-31b)
    fi
fi

ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
FRAMEWORK="${FRAMEWORK:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
MODELS_DIR="${MODELS_DIR:-$ME/models}"
ANALYSIS_PY="${ANALYSIS_PY:-$ME/envs/monitor-analysis/bin/python}"
SERVING_PY="${SERVING_PY:-/nfs/roberts/project/cpsc4880/cpsc4880_mae73/envs/monitor-vllm/bin/python}"
GEMMA_SERVING_PY="${GEMMA_SERVING_PY:-$SERVING_PY}"
SUBMIT_PY="${SUBMIT_PY:-python3}"
ACCOUNT="${ACCOUNT:-cpsc4880}"
CPU_PARTITION="${CPU_PARTITION:-day}"
GPU_PARTITION="${GPU_PARTITION:-gpu_h200}"
CPU_TIME="${CPU_TIME:-04:00:00}"
gpu_time_default=08:00:00
GPU_COUNT="${GPU_COUNT:-1}"
GPU_MEM="${GPU_MEM:-96G}"
previous="${DEPENDENCY_JOB_ID:-}"
EXPERIMENT="$FRAMEWORK/configs/experiments/qwen-gemma-baseline.toml"
batch_prefix=qwen-gemma
run_prefix=baseline
score=1
launch_blocking="${CUDA_LAUNCH_BLOCKING:-0}"
server_port="${PORT:-28474}"
if [[ "$diagnostic" == 1 ]]; then
    [[ "$parallel" == 0 ]] || { echo 'Diagnostic mode cannot use --parallel' >&2; exit 2; }
    [[ "${#monitors[@]}" == 1 && "${monitors[0]}" == qwen3-1.7b ]] || { echo 'Diagnostic mode supports only qwen3-1.7b' >&2; exit 2; }
    EXPERIMENT="$FRAMEWORK/configs/experiments/cuda-debug-qwen3-1.7b.toml"
    batch_prefix=cuda-debug
    run_prefix=cuda-debug
    enforce_eager=1
    launch_blocking=1
    server_port="${PORT:-28475}"
    GPU_COUNT=1
    gpu_time_default=02:00:00
    score=0
fi
if [[ "$parallel" == 1 ]]; then
    batch_prefix=qwen-gemma-parallel
fi
GPU_TIME="${GPU_TIME:-$gpu_time_default}"
[[ "$GPU_COUNT" =~ ^[1-9][0-9]*$ ]] || { echo "GPU_COUNT must be positive" >&2; exit 2; }
[[ -z "$previous" || "$previous" =~ ^[0-9]+$ ]] || { echo "DEPENDENCY_JOB_ID must be numeric" >&2; exit 2; }

# Validate the WHOLE selection before submitting anything. No tokenizer, weights,
# network access or inference dependencies are needed by this check.
"$SUBMIT_PY" - "$FRAMEWORK" "$EXPERIMENT" "$dry_run" "${monitors[@]}" <<'PY'
import sys
from pathlib import Path
root, experiment, dry = Path(sys.argv[1]), sys.argv[2], sys.argv[3] == '1'
sys.path.insert(0, str(root))
from monitor_experiment.registry import Registry
from monitor_experiment.spec import load_spec
from monitor_experiment import freeze
registry, spec = Registry.load(root=root), load_spec(experiment)
names = sys.argv[4:]
if len(names) != len(set(names)):
    sys.exit('Duplicate model in submission list')
for name in names:
    if name not in spec.monitors:
        sys.exit(f'{name!r} is not in {experiment}; choose from {list(spec.monitors)}')
    monitor = registry.monitor(name).runnable()
    if (monitor.context_tokens, monitor.output_reserve) != (32768, 16768):
        sys.exit(f'{name}: context/output limits differ from the completed baseline')
    if monitor.sampling != {'temperature': 0.6, 'top_p': 0.9, 'max_tokens': 16768}:
        sys.exit(f'{name}: sampling differs from the completed baseline')
if not dry:
    if not registry.reference_tokenizer.is_file():
        sys.exit(f'Missing reference tokenizer: {registry.reference_tokenizer}')
    for name in spec.rollout_sets:
        entry = registry.sets[name]
        if not (entry.root / entry.manifest).is_file():
            sys.exit(f'Missing rollout collection: {entry.root / entry.manifest}')
    freeze.require_ready(root, registry.reference_tokenizer)
PY

run_name=$("$SUBMIT_PY" -c 'import sys,tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["name"])' "$EXPERIMENT")
batch_dir="$ME/logs/$batch_prefix-$(date -u +%Y%m%dT%H%M%SZ)-$$"
receipt="$batch_dir/submissions.tsv"
if [[ "$dry_run" == 0 ]]; then
    command -v sbatch >/dev/null || { echo "Run this script on the Slurm cluster" >&2; exit 1; }
    [[ -x "$ANALYSIS_PY" ]] || { echo "Missing analysis Python: $ANALYSIS_PY" >&2; exit 1; }
    for monitor in "${monitors[@]}"; do
        serving="$SERVING_PY"
        [[ "$monitor" == gemma4-* ]] && serving="$GEMMA_SERVING_PY"
        [[ -x "$serving" ]] || { echo "Missing serving Python for $monitor: $serving" >&2; exit 1; }
        "$serving" - "$monitor" "$serving" <<'PY'
import sys
from importlib.metadata import PackageNotFoundError, version

name, executable = sys.argv[1:]
setting = "GEMMA_SERVING_PY" if name.startswith("gemma4-") else "SERVING_PY"
try:
    vllm_version = version("vllm")
except PackageNotFoundError:
    sys.exit(f"ERROR: {name}: vLLM is not installed in {executable} "
             f"(sys.executable={sys.executable}). Set {setting} to the Python "
             "executable where vLLM was installed.")
print(f"Preflight {name}: serving_python={executable} vllm={vllm_version}", flush=True)
PY
    done
    mkdir -p "$batch_dir"
    printf 'stage\tmonitor\tjob_id\tdependency\tregistry_dir\trun_dir\n' > "$receipt"
fi

submit() {
    local placeholder=$1 result
    shift
    if [[ "$dry_run" == 1 ]]; then
        printf 'DRY-RUN ' >&2
        printf '%q ' "$@" >&2
        printf '\n' >&2
        printf '%s\n' "$placeholder"
    else
        result=$("$@")
        result=${result%%;*}   # sbatch --parsable may append ;cluster
        [[ "$result" =~ ^[0-9]+$ ]] || { echo "Unexpected sbatch response: $result" >&2; return 1; }
        printf '%s\n' "$result"
    fi
}

repair_job=
gemma_lock=
if [[ "$repair_gemma" == 1 ]]; then
    gemma_lock="$ME/envs/.gemma-repair.lock"
    repair_job=$(submit REPAIR_GEMMA env ME="$ME" FRAMEWORK="$FRAMEWORK" GEMMA_SERVING_PY="$GEMMA_SERVING_PY" \
        sbatch --parsable --account="$ACCOUNT" --partition="$CPU_PARTITION" --nodes=1 --ntasks=1 \
        --cpus-per-task=4 --mem=16G --time="$CPU_TIME" --job-name=repair-gemma \
        --output="$batch_dir/repair-gemma-%j.out" --export=ALL "$FRAMEWORK/junlin/repair_gemma.sbatch")
    if [[ "$dry_run" == 0 ]]; then
        printf 'repair\tgemma-environment\t%s\t-\t-\t-\n' "$repair_job" >> "$receipt"
        printf 'Gemma environment repair=%s\n' "$repair_job"
    fi
fi

for monitor in "${monitors[@]}"; do
    registry_dir="$batch_dir/registries/$monitor"
    model_dir="$MODELS_DIR/$monitor"
    runs_dir="$ME/runs"
    port="$server_port"
    seed_baseline=
    if [[ "$parallel" == 1 ]]; then
        runs_dir="$ME/runs/parallel/$monitor"
        seed_baseline="$ME/runs/baseline"
        # Fixed registry-wide model ordering gives each model a distinct port
        # even when selections differ between submissions. Duplicate writers
        # for the same model are rejected by its run-directory lock.
        port=$("$SUBMIT_PY" - "$FRAMEWORK" "$monitor" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from monitor_experiment.registry import Registry
print(28500 + sorted(Registry.load(root=Path(sys.argv[1])).monitors).index(sys.argv[2]))
PY
)
    fi
    download_job=$(submit "DOWNLOAD_$monitor" env ME="$ME" FRAMEWORK="$FRAMEWORK" \
        ANALYSIS_PY="$ANALYSIS_PY" MONITOR="$monitor" OUT="$model_dir" REVISION="" \
        PIN_REGISTRY_DIR="$registry_dir" \
        sbatch --parsable --account="$ACCOUNT" --partition="$CPU_PARTITION" --nodes=1 --ntasks=1 \
        --cpus-per-task=4 --mem=16G --time="$CPU_TIME" --job-name="prepare-$monitor" \
        --output="$batch_dir/prepare-$monitor-%j.out" --export=ALL \
        "$FRAMEWORK/mihai/cluster/download_monitor.sbatch")
    if [[ "$dry_run" == 0 ]]; then
        printf 'prepare\t%s\t%s\t-\t%s\t%s/%s\n' "$monitor" "$download_job" "$registry_dir" "$runs_dir" "$run_name" >> "$receipt"
        printf '%s: preparation=%s\n' "$monitor" "$download_job"
    fi
    dependency="afterok:$download_job"
    [[ -n "$previous" ]] && dependency+=",afterany:$previous"
    env_lock=
    if [[ "$monitor" == gemma4-* && -n "$repair_job" ]]; then
        dependency+=",afterok:$repair_job"
        env_lock="$gemma_lock"
    fi
    serving="$SERVING_PY"
    [[ "$monitor" == gemma4-* ]] && serving="$GEMMA_SERVING_PY"
    monitor_job=$(submit "MONITOR_$monitor" env ME="$ME" FRAMEWORK="$FRAMEWORK" \
        ANALYSIS_PY="$ANALYSIS_PY" SERVING_PY="$serving" MONITOR="$monitor" \
        EXPERIMENT="$EXPERIMENT" MODEL_DIR="$model_dir" REGISTRY_DIR="$registry_dir" \
        TP="$GPU_COUNT" GPU_LABEL="H200:$GPU_COUNT" SCORE="$score" EXTRA_ARGS="" \
        ENFORCE_EAGER="$enforce_eager" CUDA_LAUNCH_BLOCKING="$launch_blocking" \
        RUNS_DIR="$runs_dir" SEED_BASELINE="$seed_baseline" GEMMA_ENV_LOCK="$env_lock" PORT="$port" \
        sbatch --parsable --account="$ACCOUNT" --partition="$GPU_PARTITION" --nodes=1 --ntasks=1 \
        --gpus="h200:$GPU_COUNT" --cpus-per-task="$((6 * GPU_COUNT))" --mem="$GPU_MEM" --time="$GPU_TIME" \
        --job-name="$run_prefix-$monitor" --dependency="$dependency" --kill-on-invalid-dep=yes \
        --output="$batch_dir/$run_prefix-$monitor-%j.out" --export=ALL \
        "$FRAMEWORK/mihai/cluster/run_monitor.sbatch")
    [[ "$parallel" == 1 ]] || previous="$monitor_job"
    printf '%s: preparation=%s monitor=%s\n' "$monitor" "$download_job" "$monitor_job"
    if [[ "$dry_run" == 0 ]]; then
        printf 'monitor\t%s\t%s\t%s\t%s\t%s/%s\n' "$monitor" "$monitor_job" "$dependency" "$registry_dir" "$runs_dir" "$run_name" >> "$receipt"
    fi
done
[[ "$dry_run" == 1 ]] || printf 'Submission receipt: %s\n' "$receipt"
