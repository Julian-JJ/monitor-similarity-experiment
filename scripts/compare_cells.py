#!/usr/bin/env python3
"""Run the pre-registered comparisons (configs/comparisons.toml) over one or more run directories.

  python scripts/compare_cells.py runs/preregistered-grid --out comparisons.json
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import compare  # noqa: E402
from monitor_experiment.artifacts import write_json  # noqa: E402
from monitor_experiment.registry import Registry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--config", default=str(ROOT / "configs/comparisons.toml"))
    parser.add_argument("--councils", default=str(ROOT / "configs/councils.toml"))
    parser.add_argument("--out", default="comparisons.json")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    registry = Registry.load()
    runs = [compare.Run(p) for p in args.runs]
    pairs = compare.pairs_for(runs, registry)
    out = compare.run_comparisons(args.config, runs, pairs, args.councils, n=args.bootstrap, seed=args.seed)
    write_json(args.out, out)
    for r in out["results"]:
        if "skipped" in r:
            print(f"SKIPPED  {r['id']} [{r.get('family')}]: {r['skipped']}")
        else:
            d = r["primary"]["difference"]
            print(f"{r['outcome']:20s} {r['id']} [{r['family']}]  diff {'n/a' if d is None else format(d, '+.3f')}  p_holm {r.get('p_holm')}")
    print("wrote", args.out)


if __name__ == "__main__":
    main()
