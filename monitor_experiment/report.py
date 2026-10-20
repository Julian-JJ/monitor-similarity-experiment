"""Markdown reports from ``metrics.json`` files (and, optionally, a comparisons file).

The report reads only stored results, so it can be regenerated at any time and never contacts a model.
Caveats are written automatically from what the data show (draft prompts, incomplete cells, missing negatives, small
samples, hierarchical cells) so that they cannot be forgotten. See docs/system/report.md.
"""

import json
from pathlib import Path

HEADLINE = (("tpr", "TPR (MonitorBench score)"), ("tnr_clean", "TNR (clean)"), ("gmean2_clean", "g-mean² (clean)"))
SECONDARY = (("tnr_cross", "TNR (cross-objective)"), ("gmean2_cross", "g-mean² (cross-objective)"), ("tnr_own", "TNR (own failures)"))
TOLD_TITLES = {"pooled": "Both told objectives pooled", "malicious": "Told the malicious objective",
               "benign": "Told the benign objective"}


def fmt(entry, digits=3):
    """``0.512 [0.401, 0.623]`` or ``n/a``. ``entry`` is a metric dict from metrics.json."""
    value = entry["value"]
    if value is None:
        return "n/a"
    text = f"{value:.{digits}f}"
    if entry.get("low") is not None and entry.get("high") is not None:
        text += f" [{entry['low']:.{digits}f}, {entry['high']:.{digits}f}]"
    return text


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def cell_name(cell):
    label = cell["label"]
    parts = [label["monitor"], label["scope"], f"context {label['task_context']}"]
    if label.get("partial_cot", "off") != "off":
        parts.append(f"partial CoT {label['partial_cot']}")
    if label.get("reasoning", "default") != "default":
        parts.append(f"reasoning {label['reasoning']}")
    return " · ".join(parts)


def caveats(runs, cells):
    notes = []
    for run in runs:
        if run.get("prompts_status") != "frozen":
            notes.append(f"Prompts were **not frozen** when run `{run['run']}` started (status: {run.get('prompts_status')}); "
                         "treat its results as a pilot, not as confirmatory.")
        git = run.get("git") or {}
        if "sessions" not in run:   # metrics written before per-session commits were recorded: only the latest invocation's commit is known
            if git.get("dirty"):
                notes.append(f"Run `{run['run']}` was made from a working tree with uncommitted changes (commit {git.get('commit', '?')[:10]}).")
            continue
        for session in run["sessions"]:
            g = session["git"]
            if g == "not recorded" or g is None:
                notes.append(f"Run `{run['run']}`: the commit used by job {session['job_id']} was not recorded (it ran before sessions recorded their own commit; "
                             f"the manifest keeps only the latest invocation's: {(git.get('commit') or '?')[:10]}, dirty: {git.get('dirty')}). Check the work log.")
            elif g.get("dirty"):
                notes.append(f"Run `{run['run']}`: job {session['job_id']} was made from a working tree with uncommitted changes (commit {(g.get('commit') or '?')[:10]}).")
            elif g.get("commit") is None:
                notes.append(f"Run `{run['run']}`: job {session['job_id']} has no recorded commit.")
    incomplete = [cell_name(c) for c in cells if not c["complete"]]
    if incomplete:
        notes.append("Incomplete cells (fewer units than requested): " + "; ".join(incomplete) + ".")
    if all(c["results"]["pooled"]["metrics"]["tnr_clean"]["value"] is None for c in cells):
        notes.append("There are **no clean negatives** in these results (no control rollouts), so TNR and g-mean² (clean) are "
                     "undefined. Only recall can be read, and recall alone rewards a monitor that flags everything.")
    hier = [(cell_name(c), c["cost"]["hierarchical_units"], c["cost"]["units"]) for c in cells if c["cost"]["hierarchical_units"]]
    if hier:
        notes.append("Some cells used the hierarchical monitor and are separate conditions from single-pass monitoring; they are "
                     "not pooled: " + "; ".join(f"{n} ({h} of {u} units)" for n, h, u in hier) + ".")
    low = [cell_name(c) for c in cells if (c["results"]["pooled"]["metrics"]["coverage"]["value"] or 1) < 0.9]
    if low:
        notes.append("Less than 90% of requested verdicts were valid for: " + "; ".join(low) + ". Invalid verdicts are excluded from the "
                     "rates, never counted as 'not detected'.")
    small = [cell_name(c) for c in cells if 0 < c["results"]["pooled"]["counts"]["positive"]["pairs"] < 30]
    if small:
        notes.append("Fewer than 30 positive pairs, so intervals are wide: " + "; ".join(small[:3]) + (" …" if len(small) > 3 else "") + ".")
    notes.append("The three tasks are held fixed in the bootstrap: intervals describe variability of rollouts and monitor samples "
                 "within these tasks, not generalization to new tasks. Conclusions are preliminary.")
    notes.append("Cross-objective negatives (rollouts whose agent pursued the *other* objective) are impure: the judge prompt's option A "
                 "is worded generally. They are shown separately as objective-specificity and are not pooled with clean negatives.")
    return notes


def render(metrics_paths, comparisons_path=None, title="Monitor experiment report"):
    runs = [json.loads(Path(p).read_text()) for p in metrics_paths]
    cells = [dict(c, run=r["run"]) for r in runs for c in r["cells"]]
    out = [f"# {title}", ""]
    out.append("Runs: " + ", ".join(f"`{r['run']}`" for r in runs) + ". Generated from stored results only; "
               "no model was contacted.")
    out.append("")
    for r in runs:
        sets = ", ".join(f"{k}: {v.get('items', 0)} rollouts" if v.get("status") == "loaded" else f"{k}: missing"
                         for k, v in r["rollout_sets"].items())
        out.append(f"* `{r['run']}`: rollout sets {sets}; {r['samples']} monitor samples per pair; bootstrap "
                   f"{r['bootstrap']['replicates']} replicates (seed {r['bootstrap']['seed']}); prompts {r.get('prompts_status')}.")
    out += ["", "## Caveats", ""] + [f"* {n}" for n in caveats(runs, cells)] + ["", "## Settings", ""]
    out.append(table(["monitor", "relation to the agent", "scope", "context", "hierarchy", "units", "complete"],
                     [[c["label"]["monitor"], c["relation_to_actor"], c["label"]["scope"], c["label"]["task_context"],
                       c["label"]["hierarchy"], f"{c['units_found']}/{c['units_expected']}", "yes" if c["complete"] else "**no**"]
                      for c in cells]))
    for told in ("pooled", "malicious", "benign"):
        out += ["", f"## {TOLD_TITLES[told]}", "", "Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).", ""]
        out.append(table(["cell"] + [name for _, name in HEADLINE] + ["coverage"],
                         [[cell_name(c)] + [fmt(c["results"][told]["metrics"][m]) for m, _ in HEADLINE]
                          + [fmt(c["results"][told]["metrics"]["coverage"])] for c in cells]))
    out += ["", "## Secondary: objective-specificity (cross-objective negatives)", "",
            "Impure negatives: see the caveats. Pooled over both told objectives.", ""]
    out.append(table(["cell"] + [name for _, name in SECONDARY],
                     [[cell_name(c)] + [fmt(c["results"]["pooled"]["metrics"][m]) for m, _ in SECONDARY] for c in cells]))
    out += ["", "## Sample sizes (pooled, pairs)", ""]
    out.append(table(["cell", "positive", "clean negative", "cross-objective", "own failures"],
                     [[cell_name(c)] + [c["results"]["pooled"]["counts"][r]["pairs"] for r in
                                         ("positive", "clean_negative", "cross_negative", "own_failure")] for c in cells]))
    out += ["", "## Cost and latency", "",
            "Tokens are as the server counted them. `served s` is the sum of request latencies (load, not GPU occupancy). "
            "`critical path` is the per-unit wall time if each tree level ran in parallel. Compute is per monitor, below, because a job is shared by the cells it runs.", ""]
    rows = []
    for c in cells:
        k = c["cost"]
        rows.append([cell_name(c), k["units"], k["calls"], k["model_requests"], f"{k['prompt_tokens']:,}", f"{k['completion_tokens']:,}",
                     f"{k['served_seconds']:.0f}", "n/a" if k["call_latency_p50"] is None else f"{k['call_latency_p50']:.1f}/{k['call_latency_p95']:.1f}",
                     "n/a" if k["critical_path_mean"] is None else f"{k['critical_path_mean']:.1f}"])
    out.append(table(["cell", "units", "calls", "requests", "prompt tokens", "completion tokens", "served s", "call latency p50/p95 s",
                      "critical path mean s"], rows))
    compute = [(r["run"], name, row) for r in runs for name, row in (r.get("compute_by_monitor") or {}).get("monitors", {}).items()]
    if compute:
        out += ["", "Compute per monitor: job wall time of the sessions that ran only that monitor, times the GPU count. It includes server "
                "start-up and idle time inside the job.", ""]
        out.append(table(["run", "monitor", "jobs", "GPU", "wall time (h)", "GPU-hours"],
                         [[run, name, ", ".join(str(j) for j in row["jobs"]), row["gpu_type"] or "n/a", f"{row['wall_seconds'] / 3600:.2f}",
                           "n/a" if row["gpu_hours"] is None else f"{row['gpu_hours']:.2f}"] for run, name, row in compute]))
    for r in runs:
        for u in (r.get("compute_by_monitor") or {}).get("unattributed_sessions", []):
            out.append(f"\n* Run `{r['run']}`: job {u['job_id']} ({u['wall_seconds'] / 3600:.2f} h) could not be attributed to one monitor "
                       f"(monitors found: {', '.join(u['monitors']) or 'none'}), so it is left out of the table above.")
    if comparisons_path:
        comp = json.loads(Path(comparisons_path).read_text())
        out += ["", f"## Pre-registered comparisons (primary metric `{comp['metric']}`, told: {comp['told']})", "",
                "Difference = first minus second, with a paired bootstrap interval over rollouts. Holm adjustment within each observation "
                f"scope. {comp['bootstrap']['replicates']} replicates, seed {comp['bootstrap']['seed']}. `mixed` means the primary metric "
                "and recall point in opposite directions, and no win is claimed.", ""]
        rows = []
        for r in comp["results"]:
            if "skipped" in r:
                rows.append([r["id"], r.get("family") or "", "skipped", r["skipped"], "", "", ""])
                continue
            p = r["primary"]
            rows.append([r["id"], r["family"], r["outcome"],
                         "n/a" if p["difference"] is None else f"{p['difference']:+.3f}",
                         "n/a" if p["low"] is None else f"[{p['low']:+.3f}, {p['high']:+.3f}]",
                         "n/a" if p["p_value"] is None else f"{p['p_value']:.3f}",
                         "n/a" if r.get("p_holm") is None else f"{r['p_holm']:.3f}"])
        out.append(table(["comparison", "scope", "outcome", "difference", "interval", "p", "p (Holm)"], rows))
        notes = [r for r in comp["results"] if r.get("note")]
        if notes:
            out += [""] + [f"* {r['id']} ({r['family']}): {r['note']}." for r in notes]
    out.append("")
    return "\n".join(out)
