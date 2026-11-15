#!/usr/bin/env bash
# Retry the unfinished models in parallel; retain the healthy Qwen3-4B result.
set -euo pipefail
retry_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$retry_root/junlin/submit_qwen_gemma_baselines.sh" --parallel --repair-gemma "$@" \
    qwen3-1.7b gemma4-e2b gemma4-e4b gemma4-12b gemma4-31b
