#!/usr/bin/env bash
# CPU-only: Jev inference is hosted by TypeSafe. No GPU/model download is needed.
#SBATCH --account=cpsc4880
#SBATCH --partition=day
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --no-requeue
set -euo pipefail
stage="${1:?prepare, full, chunks, summaries, or score}"
config="${2:?absolute config.json path}"
project="${3:?shared project directory}"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
package="$(cd -- "$(dirname -- "$config")" && pwd)"
# Remaining arguments, for example --smoke, are passed without reinterpretation.
"$project/envs/monitor-research/bin/python" -B "$package/run_jev.py" "$stage" "$config" "${@:4}"
