"""Fingerprints, the freeze lock, and the separate lock on the presence rules.

Three things, kept apart on purpose (docs/system/freeze.md):

* **Cell fingerprints** (:func:`fingerprints`) hash only what shapes what a monitor is asked and sees: the prompt files, MonitorBench's
  vendored monitor prompt, the tool lists, the objective table and the reference tokenizer. They enter every cell ID, so editing any of
  them changes every affected cell. Files that only affect how results are *read* (councils, comparisons, presence rules) are deliberately
  not here: changing them must not invalidate monitor outputs that were expensive to produce.
* **The freeze lock** (``prompts/prompts.lock.json``) covers the cell fingerprints and the pre-registered analysis definitions (councils,
  comparisons). While ``draft`` a mismatch is reported; once ``frozen`` (after the format-only pilot) it is an error and the runner refuses to start.
* **The presence-rules lock** (``configs/presence_rules.lock.json``) is separate, because the rules must stay editable until the human
  agreement check passes, which comes after the pilot (docs/plan/07-design-decisions.md 2.5).
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .artifacts import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
LOCK = "prompts/prompts.lock.json"
PROMPT_FILES = ("prompts/monitor_chunk_notice.txt", "prompts/monitor_reduce.txt", "prompts/monitor_plan.txt",
                "prompts/monitor_plan_section.txt",
                "vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml")
ANALYSIS_FILES = ("configs/councils.toml", "configs/comparisons.toml")
LOCKED_FILES = PROMPT_FILES + ANALYSIS_FILES
EXTRA_FINGERPRINTS = {"tool_lists": "configs/tool_lists.json", "objectives": "configs/objectives.json"}
RULES_FILE = "configs/presence_rules.json"
RULES_LOCK = "configs/presence_rules.lock.json"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _tokenizer_hash(root, reference_tokenizer):
    tokenizer = Path(reference_tokenizer) if reference_tokenizer else Path(root) / "cache/tokenizer/tokenizer.json"
    return sha256(tokenizer) if tokenizer.is_file() else None


def fingerprints(root=ROOT, reference_tokenizer=None):
    """Hashes of everything that shapes what a monitor is asked. These go into every cell ID."""
    root = Path(root)
    out = {"files": {name: sha256(root / name) for name in PROMPT_FILES}}
    for key, name in EXTRA_FINGERPRINTS.items():
        out[key] = sha256(root / name)
    out["tokenizer"] = _tokenizer_hash(root, reference_tokenizer)
    return out


def lock_fingerprints(root=ROOT, reference_tokenizer=None):
    """The cell fingerprints plus the pre-registered analysis definitions: what the freeze lock records."""
    root = Path(root)
    out = fingerprints(root, reference_tokenizer)
    out["files"] = {name: sha256(root / name) for name in LOCKED_FILES}
    return out


def write_lock(status, root=ROOT, reference_tokenizer=None):
    if status not in ("draft", "frozen"):
        raise ValueError("status must be 'draft' or 'frozen'")
    data = {"schema_version": 2, "status": status, "written_at": datetime.now(timezone.utc).isoformat(),
            "fingerprints": lock_fingerprints(root, reference_tokenizer)}
    write_json(Path(root) / LOCK, data)
    return data


def check(root=ROOT, reference_tokenizer=None):
    """``(status, problems)``. Problems list every file whose hash differs from the lock."""
    root = Path(root)
    path = root / LOCK
    if not path.is_file():
        return "missing", [f"{LOCK} does not exist; run scripts/freeze.py write --status draft"]
    lock = read_json(path)
    now = lock_fingerprints(root, reference_tokenizer)
    problems = []
    for name, expected in lock["fingerprints"]["files"].items():
        if now["files"].get(name) != expected:
            problems.append(f"{name} differs from the lock")
    for name in set(now["files"]) - set(lock["fingerprints"]["files"]):
        problems.append(f"{name} is locked now but was not when the lock was written")
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


# --- the presence rules have their own lock ------------------------------------------------------

def write_rules_lock(status, root=ROOT):
    if status not in ("draft", "frozen"):
        raise ValueError("status must be 'draft' or 'frozen'")
    root = Path(root)
    rules = read_json(root / RULES_FILE)
    data = {"schema_version": 1, "status": status, "written_at": datetime.now(timezone.utc).isoformat(),
            "rules_version": rules["version"], "sha256": sha256(root / RULES_FILE)}
    write_json(root / RULES_LOCK, data)
    return data


def rules_status(root=ROOT):
    """``(status, problems)`` for the presence rules. A missing lock is ``missing``; a changed file is a problem."""
    root = Path(root)
    path = root / RULES_LOCK
    if not path.is_file():
        return "missing", [f"{RULES_LOCK} does not exist"]
    lock = read_json(path)
    problems = []
    if sha256(root / RULES_FILE) != lock["sha256"]:
        problems.append(f"{RULES_FILE} differs from its lock (version {lock['rules_version']})")
    return lock["status"], problems
