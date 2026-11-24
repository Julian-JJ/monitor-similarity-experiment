#!/usr/bin/env bash
# Resume the unchanged frozen evaluator; existing case files are skipped.
#SBATCH --job-name=glide-cot-resume
#SBATCH --account=cpsc4880
#SBATCH --partition=gpu_devel,gpu_rtx6000
#SBATCH --constraint=gpu:rtx_pro_6000_blackwell
#SBATCH --gpus=1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=96G
#SBATCH --time=02:00:00
#SBATCH --no-requeue
set -euo pipefail
project="${1:?Shared project directory}"
source="${2:?Original frozen evaluation source}"

finish() {
    code=$?
    # EXIT runs even when the evaluator returns an error without a traceback.
    printf 'job=%s exit_code=%s ended_utc=%s\n' \
        "$SLURM_JOB_ID" "$code" "$(date -u +%FT%TZ)" \
        > "$project/logs/glide-cot-resume-$SLURM_JOB_ID.status"
    exit "$code"
}
trap finish EXIT
export PYTHONFAULTHANDLER=1 TORCH_SHOW_CPP_STACKTRACES=1

# These diagnostic settings do not change the model, input, or sampling settings.
bash "$source/mihai/decision_models/evaluate.sbatch" \
    "$source/mihai/decision_models/run_evaluation.py" run \
    "$source/mihai/decision_models/evaluation.json" "$project"
