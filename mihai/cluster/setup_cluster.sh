#!/usr/bin/env bash
# One-time (idempotent) preparation on a Bouchet LOGIN node for the control rollouts and for monitor runs.
# Writes only under $ME (your own project directory). The teammate's directory $SHARED is only ever read.
# See docs/system/cluster.md. Usage: bash mihai/cluster/setup_cluster.sh
set -euo pipefail

ME="${ME:-/nfs/roberts/project/cpsc4880/cpsc4880_as4833}"
SHARED="${SHARED:-/nfs/roberts/project/cpsc4880/cpsc4880_mae73}"
CHECKOUT="${CHECKOUT:-$ME/monitor-similarity-experiment}"   # must be the pristine commit that generated the cached rollouts
FRAMEWORK="${FRAMEWORK:-$ME/monitor-framework}"             # the analysis branch (helper scripts, runner)
EXPECTED_COMMIT="${EXPECTED_COMMIT:-5dc0417}"
SAMPLES_PER_TASK="${SAMPLES_PER_TASK:-12}"
SYSTEM_PYTHON="${SYSTEM_PYTHON:-/apps/software/system/software/miniconda/24.11.3/bin/python}"
RESEARCH_PY="$SHARED/envs/monitor-research/bin/python"      # read-only use: standard-library helpers only
ORIGINAL_MANIFEST="$SHARED/rollouts_original_clean/manifest.json"

say() { printf '== %s\n' "$*"; }
[[ -d "$CHECKOUT/.git" ]] || { echo "No git checkout at $CHECKOUT" >&2; exit 1; }
[[ -d "$FRAMEWORK/monitor_experiment" ]] || { echo "No framework copy at $FRAMEWORK (rsync the branch there first)" >&2; exit 1; }
[[ -x "$RESEARCH_PY" ]] || { echo "Cannot execute $RESEARCH_PY (is $SHARED readable by you?)" >&2; exit 1; }

say "1. private model directory (symlinks to the shared Qwen3-14B weights; the shared directory is not written)"
mkdir -p "$ME/models" "$ME/cache" "$ME/configs" "$ME/logs"
"$RESEARCH_PY" "$FRAMEWORK/scripts/prepare_controls.py" model-dir --shared "$SHARED/models/qwen3-14b" --private "$ME/models/qwen3-14b"

say "2. data links inside the pristine checkout (git-ignored paths, so the checkout stays clean)"
for name in models cache; do
    if [[ -L "$CHECKOUT/$name" ]]; then
        [[ "$(readlink "$CHECKOUT/$name")" == "$ME/$name" ]] || { echo "$CHECKOUT/$name links elsewhere" >&2; exit 1; }
    elif [[ -e "$CHECKOUT/$name" ]]; then
        echo "$CHECKOUT/$name exists and is not a link" >&2; exit 1
    else
        ln -s "$ME/$name" "$CHECKOUT/$name"
    fi
done

say "2b. the framework copy reads the cached rollouts (read-only link) and the pinned tokenizer, where the registries expect them"
[[ -d "$SHARED/rollouts_original_clean" ]] || { echo "No cached rollouts at $SHARED/rollouts_original_clean" >&2; exit 1; }
if [[ ! -e "$FRAMEWORK/rollouts_original_clean" ]]; then ln -s "$SHARED/rollouts_original_clean" "$FRAMEWORK/rollouts_original_clean"; fi
mkdir -p "$FRAMEWORK/cache/tokenizer"
if [[ ! -e "$FRAMEWORK/cache/tokenizer/tokenizer.json" ]]; then ln -s "$ME/models/qwen3-14b/tokenizer.json" "$FRAMEWORK/cache/tokenizer/tokenizer.json"; fi

say "3. control rollout config (the cached batch's configuration, only variants and samples changed)"
"$RESEARCH_PY" "$FRAMEWORK/scripts/prepare_controls.py" config --source "$FRAMEWORK/mihai/configs/rollouts-output-32768.toml" \
    --out "$ME/configs/rollouts-main-only.toml" --samples "$SAMPLES_PER_TASK"

say "4. is the checkout the code that generated the cached rollouts?"
"$RESEARCH_PY" "$FRAMEWORK/scripts/prepare_controls.py" verify-checkout --checkout "$CHECKOUT" --commit "$EXPECTED_COMMIT" --manifest "$ORIGINAL_MANIFEST"

say "5. analysis environment for the runner (PyYAML, tokenizers, pydantic, pandas)"
if [[ ! -x "$ME/envs/monitor-analysis/bin/python" ]]; then
    mkdir -p "$ME/envs"
    "$SYSTEM_PYTHON" -m venv "$ME/envs/monitor-analysis"
    "$ME/envs/monitor-analysis/bin/pip" install --quiet -r "$FRAMEWORK/requirements.txt" -r "$FRAMEWORK/requirements-analysis.txt"
fi
"$ME/envs/monitor-analysis/bin/python" -c "import yaml, tokenizers, pydantic, pandas; print('analysis environment ok')"
say "done"
