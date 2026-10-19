"""Build the vLLM command that serves one registered monitor. See docs/system/cluster.md.

One server serves one model, so each monitor is its own job. The server is named after the registry's ``model_id`` so the
runner's served-model check can recognise it. Nothing here starts a process: :func:`build_command` returns the argument list,
which ``scripts/serve_monitor.py`` runs (and records). Settings that have not been checked against a real server are marked
in docs/system/cluster.md: the reasoning parser for families other than Qwen3, and ``--dtype auto`` for GPT-OSS.
"""

import json
from pathlib import Path

NATIVE_CONTEXT = 32768   # Qwen3's native length; longer needs YaRN scaling


class ServingError(RuntimeError):
    pass


def dtype_for(monitor):
    """BF16 for the Qwen3 family (as the actor server uses); the model's own choice for others (GPT-OSS ships quantized)."""
    return "bfloat16" if monitor.family == "qwen3" else "auto"


def check_model_dir(model_dir):
    model_dir = Path(model_dir)
    if not (model_dir / "config.json").is_file():
        raise ServingError(f"{model_dir} has no config.json: not a downloaded model directory")
    if (model_dir / ".download-incomplete").exists():
        raise ServingError(f"{model_dir}: the download was interrupted; rerun it")
    return model_dir


def build_command(monitor, model_dir, *, python="python", host="127.0.0.1", port=8000, tensor_parallel=1,
                  max_model_len=None, yarn_factor=None, gpu_memory_utilization=0.9):
    monitor.runnable()
    max_model_len = max_model_len or monitor.context_tokens
    if max_model_len < monitor.context_tokens:
        raise ServingError(f"max_model_len {max_model_len} is below the {monitor.context_tokens} tokens of context the registry "
                           f"promises for {monitor.name!r}; the experiment's prompts would not fit")
    if max_model_len > NATIVE_CONTEXT and not yarn_factor:
        raise ServingError(f"max_model_len {max_model_len} exceeds the native {NATIVE_CONTEXT}; pass a YaRN factor (for example "
                           f"{max_model_len // NATIVE_CONTEXT}) or lower it")
    if tensor_parallel < 1 or not 0 < gpu_memory_utilization <= 1:
        raise ServingError("tensor_parallel must be at least 1 and gpu_memory_utilization in (0, 1]")
    command = [python, "-m", "vllm.entrypoints.openai.api_server", "--model", str(model_dir),
               "--served-model-name", monitor.model_id, "--host", host, "--port", str(port),
               "--dtype", dtype_for(monitor), "--tensor-parallel-size", str(tensor_parallel),
               "--max-model-len", str(max_model_len), "--gpu-memory-utilization", str(gpu_memory_utilization),
               "--generation-config", "vllm"]
    if monitor.reasoning_parser:
        command += ["--reasoning-parser", monitor.reasoning_parser]
    if yarn_factor:
        command += ["--rope-scaling", json.dumps({"rope_type": "yarn", "factor": yarn_factor,
                                                  "original_max_position_embeddings": NATIVE_CONTEXT})]
    return command


def provenance(monitor, command, vllm_version, model_dir):
    """What to record about this server alongside a run."""
    return {"schema_version": 1, "monitor": monitor.name, "monitor_identity": monitor.identity(),
            "model_dir": str(model_dir), "vllm_version": vllm_version, "command": command}
