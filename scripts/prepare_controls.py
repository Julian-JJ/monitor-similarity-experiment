#!/usr/bin/env python3
"""Prepare the pieces for generating the main_only control rollouts. See docs/system/cluster.md.

  prepare_controls.py model-dir --shared /nfs/.../models/qwen3-14b --private $ME/models/qwen3-14b
  prepare_controls.py config --source mihai/configs/rollouts-output-32768.toml --out $ME/configs/rollouts-main-only.toml --samples 12
  prepare_controls.py verify-checkout --checkout $ME/monitor-similarity-experiment --commit 5dc0417 --manifest rollouts_original_clean/manifest.json
  prepare_controls.py workers --samples 12 --block 6 [--first-sample 0]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.artifacts import read_json  # noqa: E402
from monitor_experiment.control_setup import SetupError, derive_config, link_model_dir, verify_checkout, worker_plan  # noqa: E402
from monitor_experiment.collection_builder import sha256_bytes  # noqa: E402

TASKS = ("bank_transfer_2", "american_airlines_2", "spam_filter_update")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("model-dir")
    m.add_argument("--shared", required=True)
    m.add_argument("--private", required=True)
    c = sub.add_parser("config")
    c.add_argument("--source", default=str(ROOT / "mihai/configs/rollouts-output-32768.toml"))
    c.add_argument("--out", required=True)
    c.add_argument("--samples", type=int, default=12)
    v = sub.add_parser("verify-checkout")
    v.add_argument("--checkout", required=True)
    v.add_argument("--commit", default="5dc0417")
    v.add_argument("--manifest", default=str(ROOT / "rollouts_original_clean/manifest.json"))
    w = sub.add_parser("workers")
    w.add_argument("--samples", type=int, default=12)
    w.add_argument("--block", type=int, default=6)
    w.add_argument("--first-sample", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.command == "model-dir":
            print(json.dumps(link_model_dir(args.shared, args.private), indent=2))
        elif args.command == "config":
            text = derive_config(Path(args.source).read_text(), variants=["main_only"], samples=args.samples)
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
            print(f"wrote {out}\nsha256 {sha256_bytes(out)}")
        elif args.command == "verify-checkout":
            expected = read_json(args.manifest)["runtime_implementation_hash"]
            print(json.dumps(verify_checkout(args.checkout, args.commit, expected), indent=2))
        else:
            for item in worker_plan(TASKS, args.samples, args.block, args.first_sample):
                print(f"{item['worker']} {item['task']} {item['start_sample']} {item['samples']}")
    except SetupError as error:
        sys.exit(f"ERROR: {error}")


if __name__ == "__main__":
    main()
