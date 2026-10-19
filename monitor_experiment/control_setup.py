"""Everything needed to generate the ``main_only`` control rollouts under the same conditions as the cached ones.

The controls must differ from the cached rollouts only in lacking the side objective (docs/plan/07-design-decisions.md 2.11).
This module prepares the pieces that can be checked without a GPU:

* a **private model directory** of symlinks to the shared Qwen3-14B weights (the serving script writes a manifest into the
  model directory, which the shared one does not allow), with an identical copy of the download manifest;
* a **derived rollout config**: the cached batch's config with only the variants and the sample count changed, by exact text edits;
* a **checkout check**: the code that generates must be the pristine commit whose implementation hash the cached manifest recorded;
* a **worker plan** that splits the samples across concurrent clients.

See docs/system/cluster.md.
"""

import subprocess
from pathlib import Path

from .artifacts import digest, read_json


class SetupError(RuntimeError):
    pass


def link_model_dir(shared, private):
    """Symlink every file of the download manifest into ``private`` and copy the manifest. Idempotent; returns a summary."""
    shared, private = Path(shared), Path(private)
    manifest_path = shared / "download-manifest.json"
    if not manifest_path.is_file():
        raise SetupError(f"{manifest_path} not found")
    manifest = read_json(manifest_path)
    problems = []
    for name, size in manifest["files"].items():
        target = shared / name
        if not target.is_file():
            problems.append(f"{name}: missing in the shared model directory")
        elif target.stat().st_size != size:
            problems.append(f"{name}: size {target.stat().st_size} differs from the manifest's {size}")
    if problems:
        raise SetupError("The shared model directory does not match its download manifest:\n  " + "\n  ".join(problems))
    private.mkdir(parents=True, exist_ok=True)
    for name in manifest["files"]:
        link = private / name
        target = (shared / name).resolve()
        if link.is_symlink() or link.exists():
            if link.is_symlink() and link.resolve() == target:
                continue
            raise SetupError(f"{link} already exists and is not a link to {target}")
        link.symlink_to(target)
    copy = private / "download-manifest.json"
    if copy.exists() and copy.read_bytes() != manifest_path.read_bytes():
        raise SetupError(f"{copy} differs from the shared download manifest")
    copy.write_bytes(manifest_path.read_bytes())
    return {"files": len(manifest["files"]), "bytes": sum(manifest["files"].values()), "revision": manifest["revision"],
            "manifest_sha256": digest(manifest)}


def derive_config(text, *, variants, samples):
    """The cached batch's config with only ``tasks.variants`` and ``tasks.samples`` changed (exact text edits, each expected once)."""
    edits = (('variants = ["benign", "malicious"]', "variants = [" + ", ".join(f'"{v}"' for v in variants) + "]"),
             ("samples = 8\n", f"samples = {samples}\n"))
    for old, new in edits:
        if text.count(old) != 1:
            raise SetupError(f"Expected {old!r} exactly once in the source config, found {text.count(old)}")
        text = text.replace(old, new)
    header = ("# Derived for the control rollouts: identical to the cached batch's configuration except tasks.variants and tasks.samples.\n"
              "# Do not edit by hand; the control run records this file's SHA-256.\n")
    return header + text


def worker_plan(tasks, samples_per_task, block, first_sample=0):
    """One entry per concurrent client: contiguous sample blocks per task, covering each requested sample exactly once."""
    if samples_per_task < 1 or block < 1:
        raise SetupError("samples_per_task and block must be at least 1")
    plan, worker = [], 0
    for task in tasks:
        start = first_sample
        remaining = samples_per_task
        while remaining > 0:
            count = min(block, remaining)
            plan.append({"worker": worker, "task": task, "start_sample": start, "samples": count})
            worker, start, remaining = worker + 1, start + count, remaining - count
    return plan


def pair_list(tasks, samples_per_task, first_sample=0):
    """Every (task, sample) to generate, interleaved across tasks so a partial run is balanced.

    One pair per process is the unit of isolation: a sample that fails (the generator stops its process on the first
    execution failure) must not take the other samples with it, as it did when whole blocks shared one process.
    """
    if samples_per_task < 1:
        raise SetupError("samples_per_task must be at least 1")
    return [(task, sample) for sample in range(first_sample, first_sample + samples_per_task) for task in tasks]


def implementation_hash(checkout):
    """The hash the rollout runner puts in every actor identity: every ``*.py`` under ``monitor_experiment/``."""
    folder = Path(checkout) / "monitor_experiment"
    return digest({p.name: p.read_text() for p in sorted(folder.glob("*.py"))})


def _git(checkout, *args):
    return subprocess.run(["git", *args], cwd=checkout, capture_output=True, text=True)


def checkout_state(checkout):
    """Commit, whether the code the launcher checks is unmodified, and the implementation hash."""
    commit = _git(checkout, "rev-parse", "HEAD").stdout.strip()
    paths = ["scripts", "monitor_experiment", "vendor", "configs", "prompts", "requirements.txt", "requirements-download.txt",
             "requirements-serving.txt"]
    clean = _git(checkout, "diff", "--quiet", "HEAD", "--", *paths).returncode == 0
    return {"commit": commit, "clean": clean, "implementation_hash": implementation_hash(checkout)}


def verify_checkout(checkout, expected_commit, expected_hash):
    state = checkout_state(checkout)
    problems = []
    if not state["commit"].startswith(expected_commit):
        problems.append(f"checkout is at {state['commit'][:10]}, expected {expected_commit}")
    if not state["clean"]:
        problems.append("tracked code differs from its commit")
    if state["implementation_hash"] != expected_hash:
        problems.append(f"implementation hash {state['implementation_hash'][:12]} differs from the cached batch's {expected_hash[:12]}")
    if problems:
        raise SetupError("The checkout is not the code that generated the cached rollouts: " + "; ".join(problems))
    return state
