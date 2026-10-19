"""Turn a rollout cache (the output of ``scripts/generate_rollouts.py``) into a verified collection.

The cached batch in ``rollouts_original_clean/`` was assembled on the cluster by a script that is not in this
repository. This module does the same job in the same layout, so newly generated rollouts (the ``main_only``
controls) can be loaded with :class:`monitor_experiment.data.RolloutSet` like the originals:

* keep a rollout only if its actor and its follow-up both completed, **whatever its labels**;
* copy the two files verbatim to ``<task>/<variant>/sample_NN/{rollout,followup}.json`` and check the copies' checksums;
* write ``manifest.json`` with the pairs, what was excluded and why, the generation settings and the code identity.

Nothing about a rollout's outcome decides whether it is kept; only execution status does. See docs/system/collections.md.
"""

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import digest, read_json, write_json


class CollectionError(RuntimeError):
    pass


def sha256_bytes(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scan_actors(cache, variant):
    """Every actor file for ``variant`` in the cache: ``{(task, sample): [(path, record)]}`` (retries make several)."""
    found = {}
    for path in sorted(Path(cache).glob(f"rollouts/*/{variant}/*.json")):
        record = read_json(path)
        identity = record["identity"]
        found.setdefault((identity["task"], identity["sample"]), []).append((path, record))
    return found


def build_collection(cache, out, *, variant="main_only", name, expect=None, source_job=None, hardware=None,
                     config_path=None, tasks=None, builder_path=None):
    """Assemble the collection and return the manifest. ``expect`` is the number of samples requested per task."""
    cache, out = Path(cache), Path(out)
    if (out / "manifest.json").exists():
        raise CollectionError(f"{out / 'manifest.json'} already exists; build into a new directory")
    entries = {}
    for path in sorted((cache / "entries").glob("*.json")):
        entry = read_json(path)
        if entry["variant"] == variant:
            entries[(entry["task"], entry["sample"])] = entry
    actors = scan_actors(cache, variant)
    wanted_tasks = tasks or sorted({t for t, _ in actors})
    pairs, excluded, identities = [], [], []
    keys = set(actors) | set(entries)
    if expect:
        keys |= {(t, s) for t in wanted_tasks for s in range(expect)}
    for task, sample in sorted(keys):
        entry = entries.get((task, sample))
        if entry is None:
            attempts = actors.get((task, sample), [])
            if not attempts:
                excluded.append({"task": task, "variant": variant, "sample": sample, "reason": "never started"})
            else:
                status = attempts[-1][1].get("status")
                error = attempts[-1][1].get("error") or {}
                excluded.append({"task": task, "variant": variant, "sample": sample, "rollout_id": attempts[-1][1].get("rollout_id"),
                                 "reason": f"actor {status}" + (f": {error.get('type')}: {error.get('message', '')[:200]}" if error else "")})
            continue
        actor_path = cache / entry["rollout"]
        actor = read_json(actor_path)
        followup_paths = [cache / f for f in entry["followups"]]
        reasons = []
        if actor.get("status") != "complete":
            reasons.append(f"actor {actor.get('status')}")
        if not followup_paths:
            reasons.append("no follow-up")
        followups = [read_json(p) for p in followup_paths]
        if any(f.get("status") != "complete" for f in followups):
            reasons.append("follow-up not complete")
        if len(followups) > 1:
            reasons.append("more than one follow-up (the collection format holds one)")
        if reasons:
            excluded.append({"task": task, "variant": variant, "sample": sample, "rollout_id": actor.get("rollout_id"), "reason": "; ".join(reasons)})
            continue
        directory = out / task / variant / f"sample_{sample:02d}"
        directory.mkdir(parents=True, exist_ok=True)
        copies = []
        for source, target in ((actor_path, directory / "rollout.json"), (followup_paths[0], directory / "followup.json")):
            shutil.copyfile(source, target)
            if sha256_bytes(source) != sha256_bytes(target):
                raise CollectionError(f"Copy of {source} does not match its source")
            copies.append(target)
        identity = actor["identity"]
        identities.append(identity)
        evaluation = actor["evaluation"]
        pairs.append({
            "task": task, "variant": variant, "sample": sample, "rollout_id": actor["rollout_id"],
            "followup_id": followups[0]["followup_id"],
            "actor_sha256": sha256_bytes(copies[0]), "followup_sha256": sha256_bytes(copies[1]),
            "turns": actor["turns"], "termination": actor.get("termination"),
            "main_success": evaluation["main"]["success"], "side_success": evaluation["side_success"],
            "side": evaluation["side"], "source_job_id": source_job, "hardware": hardware,
            "served_model_name": identity["model"]["serving"]["served_model_name"],
            "actor": f"{task}/{variant}/sample_{sample:02d}/rollout.json",
            "followup": f"{task}/{variant}/sample_{sample:02d}/followup.json",
            "actor_bytes": copies[0].stat().st_size, "followup_bytes": copies[1].stat().st_size})
    if not pairs:
        raise CollectionError("No complete actor-plus-follow-up pairs found")
    for key in ("generation", "runtime"):
        values = {digest(i[key] if key == "generation" else i["runtime"]["implementation_hash"]) for i in identities}
        if len(values) != 1:
            raise CollectionError(f"The collected rollouts disagree on their {key}; they were not generated under one configuration")
    served = {i["model"]["serving"]["served_model_name"] for i in identities}
    revisions = {i["model"]["revision"] for i in identities}
    if len(revisions) != 1:
        raise CollectionError(f"More than one model revision: {sorted(revisions)}")
    by_task = {}
    for p in pairs:
        by_task.setdefault(p["task"], {}).setdefault(p["variant"], 0)
        by_task[p["task"]][p["variant"]] += 1
    manifest = {
        "schema_version": 1, "collection": name, "destination": str(out),
        "selection_rule": "Keep complete actor-plus-follow-up pairs, irrespective of objective score; exclude execution failures and "
                          "incomplete or never-started samples. No monitor result or label is consulted.",
        "generation": identities[0]["generation"], "model_revision": identities[0]["model"]["revision"],
        "runtime_implementation_hash": identities[0]["runtime"]["implementation_hash"],
        "configuration_sha256": sha256_bytes(config_path) if config_path else None,
        "sources": {str(source_job): {"cache_root": str(cache), "hardware": hardware, "served_model_name": sorted(served)[0]}},
        "pairs": pairs, "excluded": excluded,
        "counts": {"requested": (expect * len(wanted_tasks)) if expect else None, "complete_pairs": len(pairs),
                   "excluded_pairs": len(excluded), "by_task": by_task},
        "builder_sha256": sha256_bytes(builder_path) if builder_path else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": {"copies_match_sources": True, "one_generation_configuration": True, "one_implementation_hash": True,
                   "one_model_revision": True, "complete_actor_followup_pairs": len(pairs)},
        "limitations": ["Complete means execution and follow-up completed, not that the model achieved any objective.",
                        "Serving identities are recorded per pair; hardware may differ from the cached batch."]}
    write_json(out / "manifest.json", manifest)
    return manifest
