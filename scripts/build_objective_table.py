#!/usr/bin/env python3
"""Write configs/objectives.json: the one text per (task, objective), read from a collection.

Fails if any (task, objective) has more than one distinct text across the collection's
samples. Run it again if the collection changes and compare the checksums.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment.data import ObjectiveTable, RolloutSet  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", default=str(ROOT / "rollouts_original_clean"))
    parser.add_argument("--output", default=str(ROOT / "configs/objectives.json"))
    args = parser.parse_args()
    collection = RolloutSet.from_manifest("source", args.collection)
    table = ObjectiveTable.build(collection.items)
    table.to_json(args.output, source=f"{Path(args.collection).name}/manifest.json "
                                     f"(sha256 {collection.manifest_sha256})")
    for (task, objective), text in sorted(table.texts.items()):
        print(f"{task:22s} {objective:10s} {len(text):5d} characters, seen in {table.counts[(task, objective)]} rollouts")
    print("wrote", args.output)


if __name__ == "__main__":
    main()
