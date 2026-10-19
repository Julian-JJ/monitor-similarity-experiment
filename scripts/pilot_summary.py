#!/usr/bin/env python3
"""Label-free summary of a run for the format-only pilot: validity, reply lengths, finish reasons, plan sizes, latency.

  pilot_summary.py runs/pilot-format-only [--json pilot-summary.json]

It never opens a rollout file and reports nothing that depends on labels. See docs/system/cluster.md and docs/plan/07 2.8.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.artifacts import write_json  # noqa: E402
from monitor_experiment.pilot import render, summarize  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir")
    parser.add_argument("--json")
    args = parser.parse_args()
    summary = summarize(args.run_dir)
    print(render(summary))
    if args.json:
        write_json(args.json, summary)


if __name__ == "__main__":
    main()
