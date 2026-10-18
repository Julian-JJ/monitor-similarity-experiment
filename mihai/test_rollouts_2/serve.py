#!/usr/bin/env python3
"""Serve existing Qwen weights with provenance written only into this experiment."""
import argparse
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from runtime.artifacts import digest, lock, read_json, write_json
from runtime.serving import make_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--port", type=int, default=28475)
    args = parser.parse_args()
    cfg = read_json(args.config)
    model = Path(args.model_dir).resolve()
    assert not (model / ".download-incomplete").exists()
    with lock(model / ".model.lock") as model_lock:
        download = read_json(model / "download-manifest.json")
        assert download["model_id"] == cfg["model_id"]
        assert download["revision"] == cfg["model_revision"]
        assert len(download["files"]) == 17
        for name, size in download["files"].items():
            assert (model / name).stat().st_size == size, name
        command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
            "--model", str(model), "--host", "127.0.0.1", "--port", str(args.port),
            "--dtype", cfg["dtype"], "--tensor-parallel-size", str(cfg["tensor_parallel_size"]),
            "--max-model-len", str(cfg["context_limit"]), "--gpu-memory-utilization", "0.9",
            "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
            "--reasoning-parser", "qwen3", "--generation-config", "vllm",
            "--rope-scaling", json.dumps({"rope_type": "yarn", "factor": cfg["yarn_factor"],
                                           "original_max_position_embeddings": 32768})]
        manifest = make_manifest({"model_id": download["model_id"], "revision": download["revision"],
            "download_manifest_hash": digest(download), "experiment": cfg["experiment"],
            "configuration_hash": digest(cfg), "vllm_version": importlib.metadata.version("vllm"),
            "command": command, "environment": {k: os.environ[k] for k in (
                "CUDA_VISIBLE_DEVICES", "VLLM_USE_V1", "VLLM_ATTENTION_BACKEND") if k in os.environ}})
        with socket.create_server(("127.0.0.1", args.port)):
            pass
        assert not Path(args.output).exists(), "Refusing to overwrite serving identity"
        write_json(args.output, manifest)
        print(json.dumps({"served_model_name": manifest["served_model_name"], "files_verified": 17}), flush=True)
        result = subprocess.run(manifest["command"], pass_fds=(model_lock,))
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
