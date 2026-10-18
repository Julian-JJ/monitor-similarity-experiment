#!/usr/bin/env python3
"""Run an explicit selection through the unchanged frozen rollout CLI, once each."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write_json(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_selection(selection):
    pairs = selection["pairs"]
    keys = [(p["task"], p["variant"], p["sample"]) for p in pairs]
    assert len(keys) == len(set(keys)) == 30
    assert sum(p["reason"] == "not_started" for p in pairs) == 26
    assert sum(p["reason"] == "interrupted_by_scheduler_timeout" for p in pairs) == 4
    assert all(t in ("bank_transfer_2", "american_airlines_2", "spam_filter_update")
               and v in ("benign", "malicious") and type(s) is int and 0 <= s < 8
               for t, v, s in keys)
    excluded = {(p["task"], p["variant"], p["sample"]) for p in selection["excluded"]}
    assert len(excluded) == 18 and not excluded.intersection(keys)
    assert len(excluded.union(keys)) == 48
    return pairs


def command(args, pair):
    return [sys.executable, str(args.source / "scripts/generate_rollouts.py"),
            "--config", str(args.config), "--base-url", args.base_url,
            "--cache-dir", str(args.cache), "--tasks", pair["task"],
            "--variants", pair["variant"], "--start-sample", str(pair["sample"]),
            "--samples", "1"]


def entry_for_pair(cache, pair, selection, serving):
    candidates = []
    for path in (cache / "entries").glob("*.json"):
        entry = json.loads(path.read_text())
        if all(entry[k] == pair[k] for k in ("task", "variant", "sample")):
            candidates.append(entry)
    assert len(candidates) == 1, "Expected exactly one completed pair entry"
    entry = candidates[0]
    actor = json.loads((cache / entry["rollout"]).read_text())
    identity = actor["identity"]
    assert actor["status"] == "complete" and actor["rollout_id"] == digest(identity)
    assert identity["runtime"]["implementation_hash"] == selection["implementation_hash"]
    assert identity["generation"] == selection["generation"]
    assert identity["model"]["serving"] == serving
    assert identity["model"]["revision"] == selection["model_revision"]
    assert identity["seed"] == selection["generation"]["seed"] + pair["sample"] * 100000
    assert len(entry["followups"]) == 1
    followup = json.loads((cache / entry["followups"][0]).read_text())
    assert followup["status"] == "complete"
    assert followup["identity"]["parent"] == actor["rollout_id"]
    assert followup["identity"]["parent_hash"] == digest(actor)
    assert followup["followup_id"] == digest(followup["identity"])
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    selection = json.loads(args.selection.read_text())
    pairs = validate_selection(selection)
    assert args.workers == 8
    if args.dry_run:
        print(json.dumps({"selected_pairs": len(pairs), "commands": [command(args, p) for p in pairs]}))
        return
    # A fresh cache keeps the old interrupted stubs and every previous result intact.
    args.cache.mkdir(parents=True, exist_ok=False)
    serving = json.loads((args.source / "models/qwen3-14b/serving-manifest.json").read_text())
    assert serving["settings"]["arguments"]["tensor_parallel_size"] == 1
    assert serving["settings"]["arguments"]["max_model_len"] == 131072
    assert serving["settings"]["arguments"]["yarn_factor"] == 4
    write_json(args.logs / f"qwen-serving-{args.job_id}.json", serving)
    records = [{**p, "state": "not_started"} for p in pairs]
    status_path = args.logs / f"qwen-selected-{args.job_id}.json"
    active, entries = {}, []

    def save():
        write_json(status_path, {"job_id": args.job_id, "updated_at": now(),
                   "selection_sha256": hashlib.sha256(args.selection.read_bytes()).hexdigest(),
                   "cache": str(args.cache), "pairs": records})

    def start(index):
        row = records[index]
        path = args.logs / f"qwen-pair-{args.job_id}-{index:02d}.log"
        with path.open("xb") as handle:
            process = subprocess.Popen(command(args, row), stdout=handle,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        active[index] = process
        row.update(state="running", started_at=now(), log=str(path))
        save()
        print(f"Started pair={index} {row['task']}/{row['variant']} sample={row['sample']}", flush=True)

    def poll():
        for index, process in list(active.items()):
            code = process.poll()
            if code is None:
                continue
            del active[index]
            row = records[index]
            row.update(exit_code=code, finished_at=now(), state="failed")
            if code == 0:
                try:
                    entry = entry_for_pair(args.cache, row, selection, serving)
                    entries.append(entry)
                    row.update(state="complete", rollout_id=entry["rollout_id"])
                except Exception as error:
                    row["validation_error"] = f"{type(error).__name__}: {error}"
            save()
            print(f"Finished pair={index} state={row['state']} exit_code={code}", flush=True)

    def stop(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    save()
    try:
        # The pilot is selected work, counted once. A pair-level failure does not
        # discard other selected work or automatically retry the failed pair.
        start(0)
        while active:
            poll()
            time.sleep(0.5)
        print(f"Pilot finished state={records[0]['state']}; starting selected queue", flush=True)
        next_index = 1
        while next_index < len(records) or active:
            while next_index < len(records) and len(active) < args.workers:
                start(next_index)
                next_index += 1
            poll()
            if active:
                time.sleep(0.5)
        manifest = {"schema_version": 1, "entries": sorted(entries, key=lambda e:
                    (e["task"], e["variant"], e["sample"]))}
        manifest_dir = args.cache / "manifests"
        manifest_dir.mkdir(exist_ok=True)
        manifest_path = manifest_dir / f"{digest(manifest)}.json"
        write_json(manifest_path, manifest)
        write_json(args.logs / f"qwen-selected-{args.job_id}-final.json",
                   {"job_id": args.job_id, "finished_at": now(), "expected_pairs": 30,
                    "complete_pairs": len(entries), "failed_pairs": 30 - len(entries),
                    "manifest": str(manifest_path), "selection": str(args.selection),
                    "pairs": records})
        if len(entries) != 30:
            raise SystemExit(1)
    finally:
        for index, process in active.items():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                records[index].update(state="interrupted", interrupted_at=now())
        save()


if __name__ == "__main__":
    main()
