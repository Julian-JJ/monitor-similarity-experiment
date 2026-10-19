"""A label-free summary of a run, for the format-only pilot (docs/plan/07-design-decisions.md 2.8).

The pilot exists to find format problems: replies that do not parse, replies cut off by the length limit, plans that are too
long, prompts that overrun the monitor's context. This module reads **only** ``items.jsonl``, ``nodes.jsonl``, ``plans/`` and
``manifest.json``. It does not import the data layer, never opens a rollout file, and reports nothing that depends on a label
or on which letter was chosen, so wording can be fixed for format without being tuned to detection performance.
"""

import json
from pathlib import Path

from .costs import percentile


def read_lines(path):
    path = Path(path)
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.is_file() else []


def quantiles(values):
    values = [v for v in values if v is not None]
    return None if not values else {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95), "max": max(values)}


def summarize(run_dir):
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text())
    items = read_lines(run_dir / "items.jsonl")
    done = {r["unit_id"] for r in items}
    nodes = [n for n in read_lines(run_dir / "nodes.jsonl") if n["unit_id"] in done]   # ignore orphans of interrupted units
    attempts = [dict(a, kind=n["kind"], level=n["level"]) for n in nodes for a in n["attempts"]]
    reasons, finishes = {}, {}
    for a in attempts:
        if not a["valid"]:
            reasons[a["reason"]] = reasons.get(a["reason"], 0) + 1
        finishes[a["finish_reason"]] = finishes.get(a["finish_reason"], 0) + 1
    by_kind = {}
    for kind in ("chunk", "reduce"):
        mine = [a for a in attempts if a["kind"] == kind]
        by_kind[kind] = {"requests": len(mine), "invalid": sum(1 for a in mine if not a["valid"]),
                         "invalid_share": (sum(1 for a in mine if not a["valid"]) / len(mine)) if mine else None}
    plans = []
    for path in sorted((run_dir / "plans").glob("*.jsonl")):
        plans += read_lines(path)
    cells = {c["cell_id"]: c for c in manifest["cells"]}
    limits = {}
    for cell in cells.values():
        monitor = manifest["monitors"][cell["label"]["monitor"]]
        limits[cell["cell_id"]] = monitor["context_tokens"] - monitor["sampling"]["max_tokens"]
    overruns = [r for r in items if r.get("max_prompt_tokens", 0) > limits.get(r["cell_id"], 10 ** 12)]
    wall = sum(s["wall_seconds"] for s in manifest.get("sessions", []))
    completion = sum(r["completion_tokens"] for r in items)
    return {
        "run": manifest["name"], "units": len(items), "units_by_status": {s: sum(1 for r in items if r["status"] == s) for s in sorted({r["status"] for r in items})},
        "requests": len(attempts), "invalid_requests": sum(1 for a in attempts if not a["valid"]),
        "invalid_reasons": reasons, "finish_reasons": finishes, "by_node_kind": by_kind,
        "requests_needing_a_retry": sum(1 for n in nodes if len(n["attempts"]) > 1),
        "reply_chars": quantiles([len(a["text"]) for a in attempts]),
        "completion_tokens_per_request": quantiles([(a.get("usage") or {}).get("completion_tokens") for a in attempts]),
        "monitor_reasoning_chars_per_request": quantiles([a.get("reasoning_chars") for a in attempts]),
        "prompt_tokens_per_request": quantiles([(a.get("usage") or {}).get("prompt_tokens") for a in attempts]),
        "prompts_over_the_monitors_input_limit": len(overruns),
        "units_chunked": sum(1 for r in items if r["hierarchical"]), "chunks_per_unit": quantiles([r["chunks"] for r in items]),
        "tree_levels": quantiles([r["levels"] for r in items]),
        "plans": {"count": len(plans), "tokens": quantiles([p["tokens"] for p in plans]),
                  "attempts_needed": quantiles([len(p["attempts"]) for p in plans])},
        "call_latency_seconds": quantiles([x for r in items for x in r.get("call_latencies", [])]),
        "critical_path_seconds": quantiles([r["critical_path_seconds"] for r in items]),
        "wall_seconds": wall or None,
        "completion_tokens_per_second": (completion / wall) if wall else None,
    }


def render(summary):
    q = lambda v: "n/a" if v is None else f"median {v['p50']:.0f}, 95th percentile {v['p95']:.0f}, max {v['max']:.0f} (n={v['n']})"
    lines = [f"Pilot summary of run `{summary['run']}` (label-free)", "",
             f"* units: {summary['units']} {summary['units_by_status']}; chunked: {summary['units_chunked']}",
             f"* requests: {summary['requests']}; invalid: {summary['invalid_requests']}; needing a retry: {summary['requests_needing_a_retry']}",
             f"* invalid share, chunk calls: {summary['by_node_kind']['chunk']['invalid_share']}; combining calls: {summary['by_node_kind']['reduce']['invalid_share']}",
             f"* invalid reasons: {summary['invalid_reasons'] or 'none'}", f"* finish reasons: {summary['finish_reasons']}",
             f"* reply length (characters): {q(summary['reply_chars'])}", f"* completion tokens per request: {q(summary['completion_tokens_per_request'])}",
             f"* monitor reasoning (characters): {q(summary['monitor_reasoning_chars_per_request'])}",
             f"* prompt tokens per request: {q(summary['prompt_tokens_per_request'])}",
             f"* prompts over the monitor's input limit: {summary['prompts_over_the_monitors_input_limit']} units",
             f"* chunks per unit: {q(summary['chunks_per_unit'])}", f"* tree levels: {q(summary['tree_levels'])}",
             f"* plans: {summary['plans']['count']}, tokens {q(summary['plans']['tokens'])}, attempts {q(summary['plans']['attempts_needed'])}",
             f"* latency per request (s): {q(summary['call_latency_seconds'])}", f"* critical path per unit (s): {q(summary['critical_path_seconds'])}",
             f"* wall time: {summary['wall_seconds']}; completion tokens per second: {summary['completion_tokens_per_second']}", ""]
    return "\n".join(lines)
