"""Run an experiment: expand the spec into units, call the monitor, store everything, resume safely.

A *unit* is one (cell, rollout, told objective, monitor sample). Each unit runs one monitor tree and
appends one line to ``items.jsonl`` and its nodes to ``nodes.jsonl``. A unit that finished, whether valid,
invalid or an error status, is final and is never rerun; a unit interrupted by a transport failure leaves no
trace and runs again on resume. Nothing that depends on labels happens here: the labels are read later, by
:func:`score_run`. See docs/system/runner.md and docs/system/run-artifacts.md.
"""

import json
import platform
import subprocess
import sys
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import freeze
from . import hierarchy as h
from . import metrics as mt
from . import spec as sp
from .artifacts import digest, read_json, write_json
from .costs import summarize
from .data import ObjectiveTable, make_pairs
from .registry import RegistryError
from .strategies import JudgeStrategy, PlanBook

SCHEMA_VERSION = 1


def now():
    return datetime.now(timezone.utc).isoformat()


class RunIncomplete(RuntimeError):
    """Some units hit transport errors and were left to rerun on resume."""


def git_state(root):
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    commit = run("rev-parse", "HEAD")
    dirty = run("status", "--porcelain")
    return {"commit": commit or None, "dirty": None if dirty is None else bool(dirty), "branch": run("branch", "--show-current")}


def limit_items(items, per_group):
    """The first ``per_group`` rollouts of each (origin, variant, task) group, in id order; 0 keeps all."""
    if per_group <= 0:
        return list(items)
    taken, out = {}, []
    for item in sorted(items, key=lambda i: i.item_id):
        if taken.get(item.group, 0) < per_group:
            taken[item.group] = taken.get(item.group, 0) + 1
            out.append(item)
    return out


def load_items(registry, set_names, item_limit=0, allow_missing=False, verify=True):
    items, info = [], {}
    for name in set_names:
        try:
            collection = registry.load_set(name, verify)
        except RegistryError:
            if not allow_missing:
                raise
            info[name] = {"status": "missing"}
            continue
        chosen = limit_items(collection.items, item_limit)
        items += chosen
        info[name] = {"status": "loaded", "manifest_sha256": collection.manifest_sha256, "items": len(chosen),
                      "available": len(collection.items), "verified": collection.verified}
    ids = [i.item_id for i in items]
    if len(ids) != len(set(ids)):
        raise RegistryError("The same rollout appears in more than one rollout set")
    return items, info


def unit_seed(base, item_id, told, sample):
    """A seed unique to the unit; tree nodes add up to a few hundred on top (nodes * 10 + attempt)."""
    return base * 10 ** 9 + (zlib.crc32(f"{item_id}|{told}".encode()) % 10 ** 5) * 10 ** 4 + sample * 10 ** 3


def unit_id(cell_id, item_id, told, sample):
    return f"{cell_id}/{item_id}/{told}/{sample}"


class JsonlWriter:
    def __init__(self, path):
        self.path, self.lock = Path(path), threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, value):
        line = json.dumps(value, ensure_ascii=False, allow_nan=False)
        with self.lock, self.path.open("a") as stream:
            stream.write(line + "\n")
            stream.flush()


def read_jsonl(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fingerprints_for(registry, root):
    return freeze.fingerprints(root, registry.reference_tokenizer)


def prepare_context(spec, registry, root, allow_missing_sets=False):
    """Everything both the dry run and the real run need, validated once."""
    prints = fingerprints_for(registry, root)
    cells = sp.expand(spec, registry, prints)
    items, sets_info = load_items(registry, spec.rollout_sets, spec.options["item_limit"], allow_missing_sets)
    objectives = ObjectiveTable.from_json(registry.objectives_table)
    return prints, cells, items, sets_info, objectives


def tool_lists_from(root):
    return read_json(Path(root) / "configs/tool_lists.json")["tools"]


def main_tasks_of(items):
    """``{task: main-task text}``; the text must be identical across a task's rollouts."""
    texts = {}
    for item in items:
        text = item.observation().main_task
        if texts.setdefault(item.task, text) != text:
            raise RegistryError(f"Task {item.task!r} has more than one main-task text; one plan per task is not valid")
    return texts


def placeholder_plan(count, tokens=800):
    words = []
    while count(" ".join(words)) < tokens:
        words.extend(["step"] * 50)
    return " ".join(words)


def dry_run(spec, registry, *, count, prompts, root, report_tokens=1000, allow_missing_sets=True):
    """Price an experiment without contacting any model. Level-0 prompts are exact; combining levels are estimated."""
    prints, cells, items, sets_info, objectives = prepare_context(spec, registry, root, allow_missing_sets)
    strategy = JudgeStrategy(prompts, count, objectives)
    plan_text = placeholder_plan(count)
    tasks = sorted({i.task for i in items})
    rows, prepared = [], {}   # planning does not depend on the monitor, so identical settings are planned once
    for cell in cells:
        calls = level0 = tree_tokens = hierarchical = units = truncated = max_prompt = 0
        text = plan_text if cell.label["task_context"] == "plan" else None
        for item in items:
            for told in spec.told:
                key = (digest(cell.params), digest(cell.partial_cot), text is not None, item.item_id, told)
                if key not in prepared:
                    prepared[key] = strategy.prepare(item, told, cell, text)
                planned = prepared[key]
                n = len(planned["chunks"])
                tree_calls, levels = h.estimate_tree(n, cell.params["bin_size"])
                overhead = count(h.reduce_prompt(prompts, planned["main_task"], planned["objective"], [(1, 1, "")], text))
                tokens = sum(c["prompt_tokens"] for c in planned["chunks"])
                samples = spec.options["samples"]
                units += samples
                calls += tree_calls * samples
                level0 += tokens * samples
                tree_tokens += h.estimate_tree_tokens(tokens, n, cell.params["bin_size"], report_tokens, overhead) * samples
                hierarchical += int(planned["hierarchical"]) * samples
                truncated += planned["truncated_tool_results"]
                max_prompt = max(max_prompt, max(c["prompt_tokens"] for c in planned["chunks"]))
        prep = len(tasks) * spec.options["prep_samples"] if cell.label["task_context"] == "plan" else 0
        rows.append({"cell_id": cell.cell_id, "label": cell.label, "units": units, "model_calls": calls,
                     "plan_calls": prep, "level0_input_tokens": level0, "input_tokens_estimate": tree_tokens,
                     "hierarchical_units": hierarchical, "max_prompt_tokens": max_prompt,
                     "truncated_tool_results": truncated})
    totals = {k: sum(r[k] for r in rows) for k in ("units", "model_calls", "input_tokens_estimate")}
    # Plans are written once per monitor, not per cell.
    plan_monitors = {r["label"]["monitor"] for r in rows if r["label"]["task_context"] == "plan"}
    totals["plan_calls"] = len(plan_monitors) * len(tasks) * spec.options["prep_samples"]
    return {"name": spec.name, "cells": rows, "totals": totals, "rollout_sets": sets_info, "items": len(items),
            "assumptions": {"report_tokens": report_tokens, "placeholder_plan_tokens": 800,
                            "note": "combining-level input and plan size are estimates; level-0 prompts are exact; "
                                    "output tokens and wall time are unknown until a monitor runs"}}


def format_dry_run(report):
    lines = [f"experiment {report['name']}: {report['items']} rollouts, rollout sets {report['rollout_sets']}",
             f"{'monitor':16s}{'scope':8s}{'context':8s}{'hier.':14s}{'units':>8s}{'calls':>9s}{'input tokens (est.)':>22s}"]
    for r in report["cells"]:
        label = r["label"]
        lines.append(f"{label['monitor']:16s}{label['scope']:8s}{label['task_context']:8s}{label['hierarchy']:14s}"
                     f"{r['units']:8d}{r['model_calls']:9d}{r['input_tokens_estimate']:22,d}")
    t = report["totals"]
    lines.append(f"{'total':16s}{'':30s}{t['units']:8d}{t['model_calls']:9d}{t['input_tokens_estimate']:22,d}"
                 f"   + {t['plan_calls']} plan calls")
    lines.append("assumptions: " + report["assumptions"]["note"])
    return "\n".join(lines)


def record_for(unit, result, planned, plan_id, seed, keep_reasoning):
    attempts = [a for n in result["nodes"] for a in n.get("attempts", ())]
    status, verdict = result["status"], result["verdict"]
    record = {"schema_version": SCHEMA_VERSION, "unit_id": unit["id"], "cell_id": unit["cell"].cell_id,
              "item_id": unit["item"].item_id, "told": unit["told"], "sample": unit["sample"], "seed": seed,
              "status": status, "letter": verdict, "detected": (verdict == "A") if status == "complete" else None,
              "hierarchical": result["hierarchical"], "chunks": len(planned["chunks"]),
              "levels": (max(n["level"] for n in result["nodes"]) + 1) if result["nodes"] else 0,
              "calls": result["calls"], "model_requests": result["model_requests"],
              "prompt_tokens": result["prompt_tokens"], "completion_tokens": result["completion_tokens"],
              "max_prompt_tokens": max([(a.get("usage") or {}).get("prompt_tokens") or 0 for a in attempts], default=0),
              "latency_seconds": result["latency_seconds"], "critical_path_seconds": result["critical_path_seconds"],
              "call_latencies": [a["latency_seconds"] for a in attempts if a.get("latency_seconds") is not None],
              "plan_id": plan_id, "partial_cot": planned.get("partial_cot"),
              "truncated_tool_results": planned["truncated_tool_results"], "finished_at": now()}
    if "error" in result:
        record["error"] = result["error"]
    nodes = []
    for node in result["nodes"]:
        kept = []
        for a in node.get("attempts", ()):
            a = dict(a)
            reasoning = a.pop("reasoning", None)
            a["reasoning_chars"] = len(reasoning) if reasoning else 0
            if keep_reasoning:
                a["reasoning"] = reasoning
            kept.append(a)
        nodes.append({"unit_id": unit["id"], **{k: v for k, v in node.items() if k != "attempts"}, "attempts": kept})
    return record, nodes


def run_experiment(spec, registry, out_root, *, make_complete, count, prompts, root, compute=None,
                   progress=print, spec_path=None):
    """Run every pending unit of ``spec``. ``make_complete(monitor, reasoning) -> (complete, provenance)``."""
    status, problems = freeze.require_ready(root, registry.reference_tokenizer)
    prints, cells, items, sets_info, objectives = prepare_context(spec, registry, root)
    for name in spec.monitors:
        registry.monitor(name).runnable()
    run_dir = Path(out_root) / spec.name
    run_dir.mkdir(parents=True, exist_ok=True)
    items_writer, nodes_writer = JsonlWriter(run_dir / "items.jsonl"), JsonlWriter(run_dir / "nodes.jsonl")
    done = {r["unit_id"] for r in read_jsonl(run_dir / "items.jsonl")}
    started = now()
    completes, provenance = {}, {}

    def complete_for(monitor_name, reasoning):
        key = (monitor_name, reasoning)
        if key not in completes:
            completes[key], provenance[f"{monitor_name}|{reasoning}"] = make_complete(registry.monitor(monitor_name), reasoning)
        return completes[key]

    for cell in cells:
        complete_for(cell.monitor, cell.label["reasoning"])
    books = {}
    plan_monitors = sorted({c.monitor for c in cells if c.label["task_context"] == "plan"})
    if plan_monitors:
        tools, main_tasks = tool_lists_from(root), main_tasks_of(items)
        for monitor_name in plan_monitors:
            monitor = registry.monitor(monitor_name)
            books[monitor_name] = PlanBook(run_dir / "plans" / f"{monitor_name}.jsonl", prompts, tools, count,
                                           monitor.identity(), spec.options["prep_samples"], spec.options["seed"])
            before = len(books[monitor_name].plans)
            made = books[monitor_name].ensure(main_tasks, complete_for(monitor_name, "default"))
            progress(f"plans for {monitor_name}: {len(made)} written, {before} reused")
    manifest = {"schema_version": SCHEMA_VERSION, "name": spec.name, "spec": spec.raw, "spec_path": str(spec_path) if spec_path else None,
                "cells": [{"cell_id": c.cell_id, "label": c.label, "params": c.params, "options": c.options,
                           "partial_cot": c.partial_cot,
                           "relation_to_actor": registry.monitor(c.monitor).relation_to(registry.actor)} for c in cells],
                "monitors": {n: registry.monitor(n).identity() for n in spec.monitors},
                "served": provenance, "actor": registry.actor.__dict__, "rollout_sets": sets_info,
                "told": list(spec.told), "samples": spec.options["samples"], "fingerprints": prints,
                "item_ids": sorted(i.item_id for i in items),
                "prompts_status": status, "prompts_problems": problems, "git": git_state(root),
                "python": platform.python_version(), "platform": platform.platform(),
                "compute": compute or {}, "started_at": started}
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        # Several invocations (for example one per monitor) share a run directory: keep every cell and session seen so far.
        earlier = read_json(manifest_path)
        manifest["sessions"] = earlier.get("sessions", [])
        seen = {x["cell_id"] for x in earlier["cells"]}
        manifest["cells"] = earlier["cells"] + [c for c in manifest["cells"] if c["cell_id"] not in seen]
        manifest["monitors"] = {**earlier.get("monitors", {}), **manifest["monitors"]}
        manifest["served"] = {**earlier.get("served", {}), **manifest["served"]}
        manifest["rollout_sets"] = {**earlier.get("rollout_sets", {}), **manifest["rollout_sets"]}
        manifest["started_at"] = earlier.get("started_at", started)
        manifest["item_ids"] = sorted(set(earlier.get("item_ids", [])) | set(manifest["item_ids"]))
    else:
        manifest["sessions"] = []
    write_json(manifest_path, manifest)
    strategy = JudgeStrategy(prompts, count, objectives)
    units = [{"id": unit_id(c.cell_id, i.item_id, t, s), "cell": c, "item": i, "told": t, "sample": s}
             for c in cells for i in items for t in spec.told for s in range(spec.options["samples"])]
    todo = [u for u in units if u["id"] not in done]
    progress(f"{len(units)} units in {len(cells)} cells; {len(units) - len(todo)} already done, {len(todo)} to run")
    planned_cache, cache_lock, errors, finished = {}, threading.Lock(), [], [0]

    def planned_for(unit):
        key = (unit["cell"].cell_id, unit["item"].item_id, unit["told"])
        with cache_lock:
            if key not in planned_cache:
                book = books.get(unit["cell"].monitor)
                plan_record = None
                if unit["cell"].label["task_context"] == "plan":
                    plan_record = book.get(unit["item"].task, unit["item"].observation().main_task, unit["item"].sample)
                planned_cache[key] = (strategy.prepare(unit["item"], unit["told"], unit["cell"],
                                                       plan_record["text"] if plan_record else None),
                                      plan_record["plan_id"] if plan_record else None)
            return planned_cache[key]

    def work(unit):
        try:
            planned, plan_id = planned_for(unit)
            seed = unit_seed(spec.options["seed"], unit["item"].item_id, unit["told"], unit["sample"])
            result = strategy.run(unit["item"], unit["told"], planned, unit["cell"],
                                  completes[(unit["cell"].monitor, unit["cell"].label["reasoning"])], seed)
            record, nodes = record_for(unit, result, planned, plan_id, seed, spec.options["keep_monitor_reasoning"])
            for node in nodes:
                nodes_writer.append(node)
            items_writer.append(record)
        except Exception as error:  # transport failures and bugs alike: leave the unit to rerun
            errors.append((unit["id"], f"{type(error).__name__}: {error}"))
            return
        with cache_lock:
            finished[0] += 1
            if finished[0] % 25 == 0 or finished[0] == len(todo):
                progress(f"{finished[0]}/{len(todo)} units")

    began = datetime.now(timezone.utc)
    with ThreadPoolExecutor(max_workers=spec.options["concurrency"]) as pool:
        list(pool.map(work, todo))
    wall = (datetime.now(timezone.utc) - began).total_seconds()
    manifest["sessions"].append({"started_at": started, "finished_at": now(), "wall_seconds": wall, "units_run": finished[0],
                                 "errors": len(errors), "compute": compute or {}})
    manifest["finished_at"] = now()
    write_json(manifest_path, manifest)
    if errors:
        write_json(run_dir / "errors.json", [{"unit_id": u, "error": e} for u, e in errors])
        raise RunIncomplete(f"{len(errors)} of {len(todo)} units failed and will rerun on resume; first: {errors[0]}")
    return run_dir


def score_run(run_dir, registry, *, bootstrap_n=2000, seed=0, verify=True):
    """Compute metrics for a finished (or partial) run; writes ``metrics.json`` and ``metrics.csv``."""
    import csv
    run_dir = Path(run_dir)
    manifest = read_json(run_dir / "manifest.json")
    records = read_jsonl(run_dir / "items.jsonl")
    items, sets_info = load_items(registry, list(manifest["rollout_sets"]), 0, allow_missing=True, verify=verify)
    if manifest.get("item_ids"):   # score only the rollouts this run used (an item_limit run uses a few)
        wanted = set(manifest["item_ids"])
        items = [i for i in items if i.item_id in wanted]
    for name, info in sets_info.items():
        if info.get("status") == "loaded":   # report how many rollouts this run used, not how many the set holds
            info["items"] = sum(1 for i in items if i.set_name == name)
    by_id = {i.item_id: i for i in items}
    pairs = {p.key: p for p in make_pairs(items, tuple(manifest["told"]))}
    sessions = manifest.get("sessions", [])
    wall = sum(s["wall_seconds"] for s in sessions) if sessions else None
    gpus = (manifest.get("compute") or {}).get("gpu_count")
    rows, cells_out = [], []
    for cell in manifest["cells"]:
        mine = [r for r in records if r["cell_id"] == cell["cell_id"] and r["item_id"] in by_id]
        collected = mt.collect(mine, pairs)
        point = mt.point_estimates(collected, pairs)
        intervals = mt.bootstrap_intervals(collected, pairs, n=bootstrap_n, seed=seed) if collected else {}
        expected = sum(1 for p in pairs.values()) * manifest["samples"]
        label = {"cell_id": cell["cell_id"], **cell["label"], "relation_to_actor": cell["relation_to_actor"]}
        rows.extend(mt.tidy_rows(label, point, intervals))
        cells_out.append({"cell_id": cell["cell_id"], "label": cell["label"], "relation_to_actor": cell["relation_to_actor"],
                          "units_expected": expected, "units_found": len(mine),
                          "complete": len(mine) == expected,
                          "results": {told: {"counts": by["counts"],
                                             "metrics": {name: {"value": v, "reason": reason, **{k: intervals.get(told, {}).get(name, {}).get(k)
                                                                                                  for k in ("low", "high", "defined")}}
                                                         for name, (v, reason) in by["metrics"].items()}}
                                      for told, by in point.items()},
                          "cost": summarize(mine, wall_seconds=wall, gpu_count=gpus)})
    out = {"schema_version": SCHEMA_VERSION, "run": manifest["name"], "told": manifest["told"], "samples": manifest["samples"],
           "prompts_status": manifest.get("prompts_status"), "git": manifest.get("git"),
           "rollout_sets": sets_info, "bootstrap": {"replicates": bootstrap_n, "seed": seed,
                                                    "level": 0.95}, "cells": cells_out}
    write_json(run_dir / "metrics.json", out)
    columns = ["cell_id", "monitor", "scope", "task_context", "hierarchy", "partial_cot", "followup_visibility", "prompt",
               "reasoning", "relation_to_actor", "told", "metric", "value", "ci_low", "ci_high", "replicates", "note"]
    with (run_dir / "metrics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return out
