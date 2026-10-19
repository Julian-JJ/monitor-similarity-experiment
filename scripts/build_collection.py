#!/usr/bin/env python3
"""Build a verified collection (manifest.json plus copied files) from a rollout cache. See docs/system/collections.md.

  build_collection.py --cache /path/to/cache --out rollouts_main_only_clean --name main_only_v1 \\
      --expect 12 --source-job 123456 --hardware "H200 x1" --config mihai/configs/rollouts-main-only.toml
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.collection_builder import CollectionError, build_collection  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", required=True, help="cache directory written by generate_rollouts.py")
    parser.add_argument("--out", required=True, help="new directory for the collection")
    parser.add_argument("--name", required=True)
    parser.add_argument("--variant", default="main_only")
    parser.add_argument("--tasks", nargs="+")
    parser.add_argument("--expect", type=int, help="samples requested per task, so missing ones are listed as excluded")
    parser.add_argument("--source-job")
    parser.add_argument("--hardware")
    parser.add_argument("--config", help="the rollout config used; its SHA-256 is recorded")
    args = parser.parse_args()
    try:
        manifest = build_collection(args.cache, args.out, variant=args.variant, name=args.name, expect=args.expect,
                                    source_job=args.source_job, hardware=args.hardware, config_path=args.config, tasks=args.tasks,
                                    builder_path=Path(__file__).resolve().parents[1] / "monitor_experiment/collection_builder.py")
    except CollectionError as error:
        sys.exit(f"ERROR: {error}")
    counts = manifest["counts"]
    print(f"{counts['complete_pairs']} complete pairs kept, {counts['excluded_pairs']} excluded"
          f"{'' if counts['requested'] is None else f' of {counts['requested']} requested'}; manifest: {Path(args.out) / 'manifest.json'}")
    for item in manifest["excluded"]:
        print(f"  excluded {item['task']}/{item['variant']}/sample_{item['sample']:02d}: {item['reason']}")
    for task, variants in sorted(counts["by_task"].items()):
        print(f"  kept {task}: {variants}")


if __name__ == "__main__":
    main()
