#!/usr/bin/env python3
"""Import compatible finalized units from the shared baseline into one model's run."""

import argparse
import dataclasses
import fcntl
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor_experiment.artifacts import write_json
from monitor_experiment.costs import sessions_by_monitor
from monitor_experiment import freeze
from monitor_experiment.registry import Registry
from monitor_experiment.spec import expand, load_spec


def seed(source, target, monitor, cell_ids):
    source, target = Path(source), Path(target)
    if (target / "manifest.json").exists() or not (source / "manifest.json").is_file():
        return 0
    # The job already holds its destination lock. Do not read a baseline being written.
    with (source / ".monitor-job.lock").open("a") as guard:
        try:
            fcntl.flock(guard, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("The original baseline is still being written; wait for that job to finish") from None
        manifest = json.loads((source / "manifest.json").read_text())
        def rows(name):
            path = source / name
            return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []
        all_items = rows("items.jsonl")
        items = [r for r in all_items if r["cell_id"] in cell_ids]
        if not items:
            return 0
        ids = {r["unit_id"] for r in items}
        if len(ids) != len(items):
            raise RuntimeError("Original baseline has duplicate unit IDs; refusing to import")
        nodes = [r for r in rows("nodes.jsonl") if r["unit_id"] in ids]
        if {r["unit_id"] for r in nodes} != ids:
            raise RuntimeError("Original baseline lacks node records for finalized units")
        selected = {**manifest, "cells": [c for c in manifest["cells"] if c["cell_id"] in cell_ids],
                    "monitors": {monitor: manifest["monitors"][monitor]},
                    "served": {k: v for k, v in manifest.get("served", {}).items() if k.startswith(monitor + "|")},
                    "sessions": [entry["session"] for entry in sessions_by_monitor(manifest, all_items)
                                 if entry["monitors"] == [monitor]]}
        target.mkdir(parents=True, exist_ok=True)
        write_json(target / "imported-baseline-manifest.json", manifest)
        for filename, records in (("items.jsonl", items), ("nodes.jsonl", nodes)):
            temporary = target / (filename + ".importing")
            temporary.write_text("".join(json.dumps(r) + "\n" for r in records))
            temporary.replace(target / filename)
        # Publish the manifest last, so an interrupted import is safely retried.
        write_json(target / "manifest.json", selected)
        return len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("source", "target", "monitor", "experiment", "registry-dir"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    registry = Registry.load(config_dir=args.registry_dir)
    spec = dataclasses.replace(load_spec(args.experiment), monitors=(args.monitor,))
    cells = expand(spec, registry, freeze.fingerprints(ROOT, registry.reference_tokenizer))
    print(f"Imported {seed(args.source, args.target, args.monitor, {c.cell_id for c in cells})} finalized units for {args.monitor}")


if __name__ == "__main__":
    main()
