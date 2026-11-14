#!/usr/bin/env bash
# Short entry point for the baseline submitter; settings restore automatically.
set -euo pipefail
run_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-}" in
    gemma) shift; set -- "$@" gemma4-e2b gemma4-e4b gemma4-12b gemma4-31b ;;
    qwen) shift; set -- "$@" qwen3-1.7b qwen3-4b ;;
esac
exec bash "$run_root/junlin/submit_qwen_gemma_baselines.sh" "$@"
