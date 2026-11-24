#!/usr/bin/env bash
#SBATCH --job-name=monitor-setup
#SBATCH --account=cpsc4880
#SBATCH --partition=day
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
# Submit from the repository root: sbatch junlin/setup.sbatch
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"
exec bash junlin/setup.sh --install "$@"
