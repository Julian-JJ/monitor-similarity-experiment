#!/usr/bin/env bash
# CPU preparation, submitted once before the parallel Gemma GPU jobs.
set -euo pipefail
cd "${FRAMEWORK:?set FRAMEWORK}"
export PYTHONDONTWRITEBYTECODE=1
bash junlin/setup.sh --repair-gemma
source "$FRAMEWORK/junlin/cuda_toolkit.sh"
export SERVING_PY="${GEMMA_SERVING_PY:?set GEMMA_SERVING_PY}"
configure_monitor_cuda
printf 'Gemma CPU preflight OK: torch_cuda=%s cuda_home=%s nvcc=%s ninja=%s\n' \
    "$MONITOR_TORCH_CUDA" "$CUDA_HOME" "$MONITOR_NVCC_VERSION" "$MONITOR_NINJA_PATH"
