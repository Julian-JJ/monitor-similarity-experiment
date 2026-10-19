#!/usr/bin/env python3
"""Show, write or verify prompts/prompts.lock.json (see docs/system/freeze.md)."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import freeze  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="report the lock status and any file that differs from it")
    write = sub.add_parser("write", help="record the current hashes")
    write.add_argument("--status", choices=("draft", "frozen"), required=True)
    args = parser.parse_args()
    if args.command == "write":
        data = freeze.write_lock(args.status)
        print(f"wrote {freeze.LOCK} with status {data['status']}")
        return
    status, problems = freeze.check()
    print("lock status:", status)
    for problem in problems:
        print("  differs:", problem)
    sys.exit(1 if (problems and status == "frozen") or status == "missing" else 0)


if __name__ == "__main__":
    main()
