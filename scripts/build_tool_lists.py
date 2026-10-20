#!/usr/bin/env python3
"""Write configs/tool_lists.json from the vendored environment source (no imports of the environment)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.artifacts import write_json  # noqa: E402
from monitor_experiment.toollists import tool_lists  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "configs/tool_lists.json"))
    args = parser.parse_args()
    lists = tool_lists()
    write_json(args.output, {"schema_version": 1, "source": "vendor/monitorbench_agent (ast, no imports)", "tools": lists})
    for task, entries in lists.items():
        print(f"{task:22s} {len(entries)} tools")
    print("wrote", args.output)


if __name__ == "__main__":
    main()
