#!/usr/bin/env python3
"""Generate rollouts one (task, sample) pair per process, a few at a time, so one failure costs one sample.

`generate_rollouts.py` stops its whole process at the first execution failure, so giving one process a block of samples loses the
rest of the block whenever one fails (about one sample in seven failed in the cached batch). This driver runs each pair in its own
process through a small pool, skips pairs already complete in the cache, and records what happened. See docs/system/cluster.md.
"""

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.collection_builder import completed_samples  # noqa: E402
from monitor_experiment.control_setup import pair_list  # noqa: E402

TASKS = ("bank_transfer_2", "american_airlines_2", "spam_filter_update")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", required=True, help="the pristine checkout whose generate_rollouts.py is run")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--config", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--log-dir", required=True)
    parser.add_argument("--variant", default="main_only")
    parser.add_argument("--tasks", nargs="+", default=list(TASKS))
    parser.add_argument("--samples", type=int, default=12, help="samples per task")
    parser.add_argument("--first-sample", type=int, default=0)
    parser.add_argument("--parallel", type=int, default=8)
    parser.add_argument("--generator", default="scripts/generate_rollouts.py", help="path relative to the checkout (overridden in tests)")
    args = parser.parse_args()
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    wanted = pair_list(args.tasks, args.samples, args.first_sample)
    done = completed_samples(args.cache_dir, args.variant) if (Path(args.cache_dir) / "entries").is_dir() else set()
    todo = [p for p in wanted if p not in done]
    print(f"{len(wanted)} pairs wanted; {len(wanted) - len(todo)} already complete in the cache; {len(todo)} to run, {args.parallel} at a time", flush=True)

    def run(pair):
        task, sample = pair
        started = time.monotonic()
        command = [args.python, args.generator, "--config", args.config, "--base-url", args.base_url, "--cache-dir", args.cache_dir,
                   "--tasks", task, "--variants", args.variant, "--start-sample", str(sample), "--samples", "1"]
        with (log_dir / f"{task}-sample{sample:02d}.log").open("w") as log:
            code = subprocess.run(command, cwd=args.checkout, stdout=log, stderr=subprocess.STDOUT).returncode
        seconds = round(time.monotonic() - started, 1)
        print(f"{'ok  ' if code == 0 else 'FAIL'} {task} sample {sample} ({seconds}s, exit {code})", flush=True)
        return {"task": task, "sample": sample, "returncode": code, "seconds": seconds}

    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        results = list(pool.map(run, todo))
    failed = [r for r in results if r["returncode"] != 0]
    summary = {"finished_at": datetime.now(timezone.utc).isoformat(), "wanted": len(wanted), "already_complete": len(wanted) - len(todo),
               "attempted": len(results), "failed": len(failed), "results": results}
    (log_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"attempted {len(results)}, failed {len(failed)}; summary in {log_dir / 'summary.json'}", flush=True)
    # Individual failures are expected (and excluded by the retention rule). Every attempt failing means something else is wrong.
    sys.exit(1 if results and len(failed) == len(results) else 0)


if __name__ == "__main__":
    main()
