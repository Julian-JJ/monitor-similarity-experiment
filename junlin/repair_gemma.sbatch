#!/usr/bin/env bash
# CPU preparation, submitted once before the parallel Gemma GPU jobs.
set -euo pipefail
cd "${FRAMEWORK:?set FRAMEWORK}"
exec bash junlin/setup.sh --repair-gemma
