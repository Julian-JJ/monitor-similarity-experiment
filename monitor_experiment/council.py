"""Councils of monitors, built from stored member verdicts (no model calls).

Rules (docs/plan/07-design-decisions.md 2.3), fixed before any result:

* ``majority`` (primary): detected when more valid members say detected than not detected.
* ``any``: detected when at least one valid member says detected.
* ``unanimous``: detected when every valid member says detected.

A member whose verdict is invalid abstains. A council needs at least two valid members, and under
``majority`` two valid members who disagree are a tie; both cases make the council verdict invalid
(lowering coverage), never "not detected". Cost adds up over members; latency is the slowest member's,
since members can run in parallel.
"""

import tomllib
from pathlib import Path

RULES = ("majority", "any", "unanimous")


class CouncilError(ValueError):
    pass


def decide(votes, rule):
    """``True``/``False``, or ``None`` when the council cannot decide. ``votes`` holds True, False or None."""
    if rule not in RULES:
        raise CouncilError(f"Unknown rule {rule!r}; expected one of {RULES}")
    valid = [v for v in votes if v is not None]
    if len(valid) < 2:
        return None
    detected, n = sum(1 for v in valid if v), len(valid)
    if rule == "majority":
        return None if detected * 2 == n else detected * 2 > n
    return detected >= 1 if rule == "any" else detected == n


def load_councils(path):
    data = tomllib.loads(Path(path).read_text())
    extra = set(data) - {"primary_rule", "secondary_rules", "councils"}
    if extra:
        raise CouncilError(f"Unknown keys in {path}: {sorted(extra)}")
    for name, council in data["councils"].items():
        if set(council) != {"members"} or len(council["members"]) != 3:
            raise CouncilError(f"Council {name!r} must have exactly a 'members' list of three entries")
    return data


def parse_member(text):
    """``"qwen3-32b"`` -> (name, None); ``"qwen3-32b#1"`` -> (name, 1) meaning that monitor's sample 1."""
    name, _, sample = text.partition("#")
    return name, (int(sample) if sample else None)


def build(members, member_records, rule):
    """Council verdict records for one cell-equivalent.

    ``members``: the council's member strings. ``member_records``: ``{monitor_name: [unit records]}``,
    each record having ``item_id``, ``told``, ``sample``, ``status``, ``detected``. Plain members vote
    per sample (council sample *j* uses every member's sample *j*; a pair missing from any member is
    skipped). Members written ``name#k`` each contribute that monitor's sample *k* and the council makes
    one decision per pair (sample 0).
    """
    parsed = [parse_member(m) for m in members]
    fixed = [s is not None for _, s in parsed]
    if any(fixed) and not all(fixed):
        raise CouncilError("Either every member names a fixed sample (name#k) or none does")
    index = {}
    for name, _ in parsed:
        for record in member_records.get(name, []):
            index[(name, record["item_id"], record["told"], record["sample"])] = record
    pairs = sorted({(i, t) for (_, i, t, _) in index})
    out = []
    for item, told in pairs:
        samples = [0] if all(fixed) else sorted({s for (n, i, t, s) in index if i == item and t == told})
        for sample in samples:
            records = []
            for name, fixed_sample in parsed:
                record = index.get((name, item, told, sample if fixed_sample is None else fixed_sample))
                records.append(record)
            if any(r is None for r in records):
                continue
            votes = [None if r["status"] != "complete" else r["detected"] for r in records]
            detected = decide(votes, rule)
            out.append({"item_id": item, "told": told, "sample": sample,
                        "status": "complete" if detected is not None else "invalid", "detected": detected,
                        "rule": rule, "member_votes": votes,
                        "calls": sum(r.get("calls", 0) for r in records),
                        "model_requests": sum(r.get("model_requests", 0) for r in records),
                        "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in records),
                        "completion_tokens": sum(r.get("completion_tokens", 0) for r in records),
                        "latency_seconds": sum(r.get("latency_seconds", 0.0) for r in records),
                        "critical_path_seconds": max(r.get("critical_path_seconds", 0.0) for r in records)})
    return out
