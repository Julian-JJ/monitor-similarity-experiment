#!/usr/bin/env bash
# SBATCH lines ask Slurm for a CPU allocation; no GPU is reserved here.
#SBATCH --job-name=glide-install
#SBATCH --account=cpsc4880
#SBATCH --partition=devel
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --no-requeue
set -euo pipefail
export PROJECT="${1:?Shared project directory required}"
bash "${2:?Absolute setup_glide.sh path required}"
