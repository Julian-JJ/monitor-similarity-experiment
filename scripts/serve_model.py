#!/usr/bin/env python3
"""Start a Qwen3 thinking/tool-calling vLLM server on the cluster."""

import argparse
import importlib.metadata
import json
import math
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor_experiment.artifacts import digest, lock, read_json, write_json
from monitor_experiment.serving import make_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", default=str(ROOT / "models/qwen3-14b"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--max-model-len", type=int, default=32768)
    parser.add_argument("--yarn-factor", type=float, help="Optional long-context RoPE scaling (e.g. 2 or 4)")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    args = parser.parse_args()
    if args.tensor_parallel_size < 1 or args.max_model_len < 1 or not 0 < args.gpu_memory_utilization <= 1:
        parser.error("Invalid GPU count, context length, or GPU memory utilization")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.yarn_factor is not None and (not math.isfinite(args.yarn_factor) or args.yarn_factor <= 1):
        parser.error("yarn-factor must exceed 1")
    model_dir = Path(args.model_dir).expanduser().resolve()
    args.model_dir = str(model_dir)
    # A repository-wide lock also rejects servers using different model paths.
    # The model lock protects against another checkout or a concurrent download.
    with lock(ROOT / ".runtime/actor-server.lock") as repo_lock, \
         lock(model_dir / ".model.lock") as model_lock:
        launch(parser, args, model_dir, (repo_lock, model_lock))


def launch(parser, args, model_dir, lock_fds):
    if (model_dir / ".download-incomplete").exists():
        parser.error("Model download was interrupted; rerun download_model.py first")
    manifest = read_json(model_dir / "download-manifest.json")
    if manifest["model_id"] != "Qwen/Qwen3-14B":
        parser.error("Expected a Qwen3-14B download manifest")
    for name, size in manifest["files"].items():
        file = model_dir / name
        if not file.is_file() or file.stat().st_size != size:
            parser.error(f"Missing or changed downloaded file: {name}")
    try:
        serving_version = importlib.metadata.version("vllm")
    except importlib.metadata.PackageNotFoundError:
        parser.error("Install requirements-serving.txt in the GPU serving environment")
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
               "--model", str(model_dir),
               "--host", args.host, "--port", str(args.port),
               "--dtype", "bfloat16", "--tensor-parallel-size", str(args.tensor_parallel_size),
               "--max-model-len", str(args.max_model_len),
               "--gpu-memory-utilization", str(args.gpu_memory_utilization),
               "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
               "--reasoning-parser", "qwen3", "--generation-config", "vllm"]
    if args.yarn_factor is not None:
        command += ["--rope-scaling", json.dumps({"rope_type": "yarn", "factor": args.yarn_factor,
                                                  "original_max_position_embeddings": 32768})]
    serving = make_manifest({
        "model_id": manifest["model_id"], "revision": manifest["revision"],
        "download_manifest_hash": digest(manifest),
        "vllm_version": serving_version, "arguments": vars(args), "command": command,
        "environment": {name: os.environ[name] for name in (
            "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER", "VLLM_USE_V1",
            "VLLM_ATTENTION_BACKEND", "VLLM_WORKER_MULTIPROC_METHOD",
            "PYTHONHASHSEED", "CUBLAS_WORKSPACE_CONFIG", "NVIDIA_TF32_OVERRIDE")
            if name in os.environ}})
    # Catch occupied ports before replacing provenance. The model name check
    # also prevents accepting a different server if a bind race occurs later.
    family = socket.AF_INET6 if ":" in args.host else socket.AF_INET
    try:
        with socket.create_server((args.host, args.port), family=family):
            pass
    except OSError as error:
        parser.error(f"Cannot reserve server address {args.host}:{args.port}: {error}")
    write_json(model_dir / "serving-manifest.json", serving)
    print(json.dumps(serving["command"]), flush=True)
    # Keep the launcher alive and pass the locks to the child. If the launcher
    # is killed, the running server still owns them until it exits.
    result = subprocess.run(serving["command"], pass_fds=lock_fds)
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
