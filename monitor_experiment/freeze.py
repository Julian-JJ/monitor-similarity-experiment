"""Fingerprints and the freeze lock for everything that must not change once monitors run.

``fingerprints`` hashes the prompt files, the reference tokenizer, the tool lists and the objective table;
cell IDs include these hashes, so editing any of them changes every affected cell. ``prompts/prompts.lock.json``
records the hashes with a status. While ``draft`` a mismatch is only reported; once ``frozen``
(after the format-only pilot) a mismatch is an error and the runner refuses to start.
See docs/system/freeze.md and docs/plan/07-design-decisions.md 2.8.
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
LOCK = "prompts/prompts.lock.json"
LOCKED_FILES = ("prompts/monitor_chunk_notice.txt", "prompts/monitor_reduce.txt", "prompts/monitor_plan.txt",
                "prompts/monitor_plan_section.txt",
                "vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml",
                "configs/councils.toml", "configs/presence_rules.json", "configs/comparisons.toml")
EXTRA_FINGERPRINTS = {"tool_lists": "configs/tool_lists.json", "objectives": "configs/objectives.json"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprints(root=ROOT, reference_tokenizer=None):
    root = Path(root)
    out = {"files": {name: sha256(root / name) for name in LOCKED_FILES}}
    for key, name in EXTRA_FINGERPRINTS.items():
        out[key] = sha256(root / name)
    tokenizer = Path(reference_tokenizer) if reference_tokenizer else root / "cache/tokenizer/tokenizer.json"
    out["tokenizer"] = sha256(tokenizer) if tokenizer.is_file() else None
    return out


def write_lock(status, root=ROOT, reference_tokenizer=None):
    if status not in ("draft", "frozen"):
        raise ValueError("status must be 'draft' or 'frozen'")
    data = {"schema_version": 1, "status": status, "written_at": datetime.now(timezone.utc).isoformat(),
            "fingerprints": fingerprints(root, reference_tokenizer)}
    write_json(Path(root) / LOCK, data)
    return data


def check(root=ROOT, reference_tokenizer=None):
    """``(status, problems)``. Problems list every file whose hash differs from the lock."""
    root = Path(root)
    path = root / LOCK
    if not path.is_file():
        return "missing", [f"{LOCK} does not exist; run scripts/freeze.py write --status draft"]
    lock = read_json(path)
    now = fingerprints(root, reference_tokenizer)
    problems = []
    for name, expected in lock["fingerprints"]["files"].items():
        if now["files"].get(name) != expected:
            problems.append(f"{name} differs from the lock")
    for key in list(EXTRA_FINGERPRINTS) + ["tokenizer"]:
        if now[key] != lock["fingerprints"][key]:
            problems.append(f"{key} differs from the lock")
    return lock["status"], problems


def require_ready(root=ROOT, reference_tokenizer=None):
    """For the runner. Returns the lock status; raises if a frozen lock is violated."""
    status, problems = check(root, reference_tokenizer)
    if status == "frozen" and problems:
        raise RuntimeError("Frozen files changed since the freeze:\n  " + "\n  ".join(problems) +
                           "\nChanges after the freeze are amendments (docs/plan/07-design-decisions.md).")
    return status, problems
