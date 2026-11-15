# Sourced by the GPU job: FlashInfer may compile kernels during server startup.
# Loading a module here keeps this independent of the submitter's login shell.

monitor_nvcc_version() {
    local output
    output=$("$1" --version) || return 1
    [[ "$output" =~ release[[:space:]]+([0-9]+\.[0-9]+), ]] || return 1
    printf '%s\n' "${BASH_REMATCH[1]}"
}

configure_monitor_cuda() {
    local nvcc= current= module_name= module_init resolved_nvcc serving_bin
    local module_initializers=(/etc/profile.d/lmod.sh /etc/profile.d/modules.sh)
    serving_bin=$(dirname -- "$(command -v -- "$SERVING_PY")") || return 1
    # Using an absolute venv Python does not activate its command-line tools.
    export PATH="$serving_bin:$PATH"
    MONITOR_TORCH_CUDA=$("$SERVING_PY" -c 'import torch; print(torch.version.cuda)') || return 1
    [[ "$MONITOR_TORCH_CUDA" =~ ^[0-9]+\.[0-9]+$ ]] || {
        echo "Serving Python has no recognizable CUDA runtime: $MONITOR_TORCH_CUDA" >&2
        return 1
    }
    if [[ -n "${CUDA_HOME:-}" && -x "$CUDA_HOME/bin/nvcc" ]]; then
        nvcc="$CUDA_HOME/bin/nvcc"
    elif [[ -n "${CUDA_PATH:-}" && -x "$CUDA_PATH/bin/nvcc" ]]; then
        nvcc="$CUDA_PATH/bin/nvcc"
    else
        nvcc=$(command -v nvcc || true)
    fi
    [[ -z "$nvcc" ]] || current=$(monitor_nvcc_version "$nvcc" || true)
    MONITOR_CUDA_MODULE='existing toolkit'
    if [[ -n "${CUDA_MODULE:-}" || "$current" != "$MONITOR_TORCH_CUDA" ]]; then
        if ! command -v module >/dev/null; then
            if [[ "${LMOD_CMD:-}" == */libexec/lmod ]]; then
                module_initializers=("${LMOD_CMD%/libexec/lmod}/init/bash" "${module_initializers[@]}")
            fi
            for module_init in "${module_initializers[@]}"; do
                [[ -r "$module_init" ]] || continue
                source "$module_init"
                command -v module >/dev/null && break
            done
        fi
        module_name="${CUDA_MODULE:-CUDA/$MONITOR_TORCH_CUDA}"
        if ! command -v module >/dev/null || ! module load "$module_name"; then
            echo "Cannot load $module_name for torch CUDA $MONITOR_TORCH_CUDA. Run 'module spider CUDA' on Bouchet; set CUDA_MODULE to a matching module or CUDA_HOME to its toolkit directory." >&2
            return 1
        fi
        MONITOR_CUDA_MODULE="$module_name"
        nvcc=$(command -v nvcc || true)
        current=
        [[ -z "$nvcc" ]] || current=$(monitor_nvcc_version "$nvcc" || true)
    fi
    if [[ -z "$nvcc" || "$current" != "$MONITOR_TORCH_CUDA" ]]; then
        echo "Need nvcc $MONITOR_TORCH_CUDA for the serving environment; found ${current:-no usable nvcc} at ${nvcc:-no path}. Check 'module spider CUDA' and CUDA_MODULE." >&2
        return 1
    fi
    resolved_nvcc=$(readlink -f -- "$nvcc") || return 1
    CUDA_HOME=$(dirname -- "$(dirname -- "$resolved_nvcc")") || return 1
    export CUDA_HOME
    export CUDA_PATH="$CUDA_HOME" CUDACXX="$CUDA_HOME/bin/nvcc"
    export PATH="$CUDA_HOME/bin:$serving_bin:$PATH"
    MONITOR_NVCC_VERSION="$current"
    MONITOR_NINJA_PATH=$(command -v ninja || true)
    if [[ -z "$MONITOR_NINJA_PATH" ]] || ! MONITOR_NINJA_VERSION=$("$MONITOR_NINJA_PATH" --version); then
        echo "FlashInfer needs ninja on PATH. Run the Gemma repair prerequisite to install it in the serving environment: bash junlin/retry.sh gemma" >&2
        return 1
    fi
}
