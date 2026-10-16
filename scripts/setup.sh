#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"
INSTALL_SERVING=0
for arg in "$@"; do
    case "$arg" in
        --with-serving) INSTALL_SERVING=1 ;;
        *) echo "Usage: bash scripts/setup.sh [--with-serving]" >&2; exit 2 ;;
    esac
done
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/requirements.txt" -r "$REPO_ROOT/requirements-download.txt"
if [[ "$INSTALL_SERVING" == 1 ]]; then
    "$VENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/requirements-serving.txt"
fi
"$VENV_DIR/bin/python" "$REPO_ROOT/scripts/generate_rollouts.py" --check-environments
"$VENV_DIR/bin/python" -m pip freeze > "$VENV_DIR/installed-requirements.txt"
echo "Setup complete. No model weights have been downloaded."
echo "Next: $VENV_DIR/bin/python $REPO_ROOT/scripts/download_model.py"
