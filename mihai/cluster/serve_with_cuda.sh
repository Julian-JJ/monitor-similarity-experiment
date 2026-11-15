#!/usr/bin/env bash
# Configure the actual server process, including when its sbatch snapshot is old.
set -euo pipefail
cuda_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
export SERVING_PY="${1:?serving Python required}"
cuda_manifest="${2-}"
shift 2
source "$cuda_root/mihai/cluster/cuda_toolkit.sh"
configure_monitor_cuda
"$SERVING_PY" - "$cuda_root" "$cuda_manifest" "$MONITOR_TORCH_CUDA" "$MONITOR_NVCC_VERSION" "$MONITOR_CUDA_MODULE" "$MONITOR_NINJA_VERSION" <<'PY'
import json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from monitor_experiment.artifacts import write_json
environment = {
    'python': sys.executable, 'torch_cuda': sys.argv[3], 'nvcc_version': sys.argv[4],
    'cuda_module': sys.argv[5], 'ninja_version': sys.argv[6],
    'cuda_home': os.environ['CUDA_HOME'], 'cuda_path': os.environ['CUDA_PATH'],
    'nvcc': shutil.which('nvcc'), 'ninja': shutil.which('ninja'),
    'loaded_modules': os.environ.get('LOADEDMODULES', ''),
}
if sys.argv[2]:
    path = Path(sys.argv[2])
    record = json.loads(path.read_text())
    record['cuda_environment'] = environment
    write_json(path, record)
print(json.dumps({'cuda_environment': environment}), flush=True)
PY
exec "$@"
