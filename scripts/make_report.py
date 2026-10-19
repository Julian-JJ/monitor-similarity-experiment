#!/usr/bin/env python3
"""Write a Markdown report from one or more runs' metrics.json files.

  python scripts/make_report.py runs/baseline/metrics.json --comparisons comparisons.json --out report.md
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.report import render  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metrics", nargs="+", help="metrics.json files (from scripts/score_run.py or --score)")
    parser.add_argument("--comparisons", help="comparisons.json from scripts/compare_cells.py")
    parser.add_argument("--title", default="Monitor experiment report")
    parser.add_argument("--out", default="report.md")
    args = parser.parse_args()
    Path(args.out).write_text(render(args.metrics, args.comparisons, args.title))
    print("wrote", args.out)


if __name__ == "__main__":
    main()
