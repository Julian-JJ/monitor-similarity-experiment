#!/usr/bin/env python3
"""Compute metrics for a run directory: runs/<name>/metrics.json and metrics.csv (needs the rollouts for labels)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import runner  # noqa: E402
from monitor_experiment.registry import Registry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-verify", action="store_true", help="skip rollout checksum verification")
    args = parser.parse_args()
    out = runner.score_run(args.run_dir, Registry.load(), bootstrap_n=args.bootstrap, seed=args.seed, verify=not args.no_verify)
    for cell in out["cells"]:
        pooled = cell["results"]["pooled"]["metrics"]
        show = lambda name: "n/a" if pooled[name]["value"] is None else f"{pooled[name]['value']:.3f}"
        print(f"{cell['label']['monitor']:14s} {cell['label']['scope']:7s} {cell['label']['task_context']:5s} "
              f"tpr {show('tpr')}  tnr_clean {show('tnr_clean')}  gmean2_clean {show('gmean2_clean')}  coverage {show('coverage')}"
              f"{'' if cell['complete'] else '  [incomplete: %d of %d units]' % (cell['units_found'], cell['units_expected'])}")
    print("wrote", Path(args.run_dir) / "metrics.json", "and metrics.csv")


if __name__ == "__main__":
    main()
