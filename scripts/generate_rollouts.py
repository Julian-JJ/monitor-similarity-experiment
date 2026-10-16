#!/usr/bin/env python3
"""Generate real simulated-environment rollouts from a running inference server."""

import argparse
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.artifacts import read_json
from monitor_experiment.environments import Environment, TASKS
from monitor_experiment.inference import Client
from monitor_experiment.rollouts import generate


def resolve(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/rollouts.toml")
    parser.add_argument("--tasks", nargs="+", choices=TASKS)
    parser.add_argument("--variants", nargs="+", choices=("benign", "malicious", "main_only"))
    parser.add_argument("--samples", type=int)
    parser.add_argument("--start-sample", type=int, default=0, help="Shard samples across cluster jobs")
    parser.add_argument("--followup-samples", type=int)
    parser.add_argument("--base-url")
    parser.add_argument("--cache-dir")
    parser.add_argument("--check-environments", action="store_true", help="Validate tools/evaluators without a model")
    args = parser.parse_args()
    config = tomllib.loads(resolve(args.config).read_text())
    tasks = args.tasks or config["tasks"]["names"]
    variants = args.variants or config["tasks"]["variants"]
    if any(t not in TASKS for t in tasks) or any(v not in ("benign", "malicious", "main_only") for v in variants):
        parser.error("Unsupported task or variant in config")
    if args.check_environments:
        for task in tasks:
            env = Environment(task, "benign", 42)
            print(task, len(env.tools()), "tools", env.evaluate())
        return
    samples = args.samples if args.samples is not None else config["tasks"]["samples"]
    if args.followup_samples is not None:
        config["followup"]["samples"] = args.followup_samples
    if samples < 1 or args.start_sample < 0 or config["followup"]["samples"] < 0:
        parser.error("Samples must be positive; start/follow-up samples must be nonnegative")
    for name in ("max_tokens", "max_turns", "timeout"):
        if config["generation"][name] <= 0:
            parser.error(f"generation.{name} must be positive")
    if config["followup"]["max_tokens"] <= 0:
        parser.error("followup.max_tokens must be positive")
    manifest = read_json(resolve(config["model"]["manifest"]))
    if manifest["model_id"] != config["model"]["id"]:
        parser.error("Downloaded model manifest does not match configured model")
    config["model"]["revision"] = manifest["revision"]
    config["model"]["download_manifest"] = manifest
    serving = read_json(resolve(config["model"]["serving_manifest"]))
    if (serving["revision"], serving["model_id"]) != (manifest["revision"], manifest["model_id"]):
        parser.error("Serving manifest and downloaded model revision disagree")
    config["model"]["serving"] = serving
    if args.base_url:
        config["model"]["base_url"] = args.base_url
    client = Client(config["model"]["base_url"], config["model"]["id"],
                    config["generation"]["timeout"], config["model"]["api_key_env"])
    print("Endpoint:", client.check())
    generate(config, client, resolve(args.cache_dir or config["cache"]["directory"]),
             tasks, variants, samples, args.start_sample)


if __name__ == "__main__":
    main()
