#!/usr/bin/env python3
"""Serve one registered monitor with vLLM (one model per server). See docs/system/cluster.md.

  serve_monitor.py --monitor qwen3-32b --model-dir $MODELS/qwen3-32b --port 8000 --manifest logs/serving-qwen3-32b.json
  serve_monitor.py --monitor qwen3-32b --model-dir ... --print-command      # show the command only
"""

import argparse
import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.artifacts import write_json  # noqa: E402
from monitor_experiment.monitor_serving import ServingError, build_command, check_model_dir, provenance  # noqa: E402
from monitor_experiment.registry import Registry, RegistryError  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monitor", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--max-model-len", type=int)
    parser.add_argument("--yarn-factor", type=float)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.9)
    parser.add_argument("--manifest", help="write what is being served (command, vLLM version, monitor identity) here")
    parser.add_argument("--print-command", action="store_true")
    args = parser.parse_args()
    try:
        monitor = Registry.load().monitor(args.monitor)
        model_dir = check_model_dir(args.model_dir)
        command = build_command(monitor, model_dir.resolve(), python=sys.executable, host=args.host, port=args.port,
                                tensor_parallel=args.tensor_parallel_size, max_model_len=args.max_model_len,
                                yarn_factor=args.yarn_factor, gpu_memory_utilization=args.gpu_memory_utilization)
    except (ServingError, RegistryError) as error:
        sys.exit(f"ERROR: {error}")
    if args.print_command:
        print(json.dumps(command))
        return
    try:
        version = importlib.metadata.version("vllm")
    except importlib.metadata.PackageNotFoundError:
        sys.exit("ERROR: vllm is not installed in this Python; use the GPU serving environment")
    if args.manifest:
        write_json(args.manifest, provenance(monitor, command, version, model_dir.resolve()))
    print(json.dumps(command), flush=True)
    sys.exit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
