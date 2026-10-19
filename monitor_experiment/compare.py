"""The pre-registered comparisons (P1 to P5): select cells by label, compare them pair against pair.

``configs/comparisons.toml`` names the comparisons by the *settings* of the two cells (a monitor, a scope,
a context), not by cell IDs, so the file can be written before any run exists. Councils are virtual cells built
from stored member verdicts (:mod:`monitor_experiment.council`). Results carry the paired difference with its
bootstrap interval, the primary-versus-recall outcome (``A better``, ``B better``, ``mixed``, ``no clear
difference``) and Holm-adjusted p-values, with Holm applied within each observation scope. See docs/system/comparisons.md.
"""

import tomllib
from pathlib import Path

from . import council as cn
from . import metrics as mt
from .artifacts import read_json
from .runner import read_jsonl

LABEL_KEYS = ("monitor", "scope", "task_context", "hierarchy", "partial_cot", "reasoning")


class CompareError(ValueError):
    pass


class Run:
    """A finished run directory: its manifest and unit records."""

    def __init__(self, path):
        self.path = Path(path)
        self.manifest = read_json(self.path / "manifest.json")
        self.records = read_jsonl(self.path / "items.jsonl")

    def cells(self):
        return self.manifest["cells"]

    def records_of(self, cell_id):
        return [r for r in self.records if r["cell_id"] == cell_id]


def pairs_for(runs, registry, verify=True):
    """The pair table (labels and roles) for every rollout set the given runs used."""
    from .data import make_pairs
    from .runner import load_items
    names = sorted({name for run in runs for name in run.manifest["rollout_sets"]})
    told = tuple(runs[0].manifest["told"])
    items, _ = load_items(registry, names, 0, allow_missing=True, verify=verify)
    return {p.key: p for p in make_pairs(items, told)}


def select(runs, selector):
    """The one (run, cell) whose label contains every key in ``selector``."""
    found = [(run, cell) for run in runs for cell in run.cells()
             if all(cell["label"].get(k) == v for k, v in selector.items())]
    if len(found) != 1:
        raise CompareError(f"Selector {selector} matches {len(found)} cells; it must match exactly one")
    return found[0]


def virtual_cells(runs, councils, rule, base):
    """Council cells for every setting shared by all of a council's members; ``{name: (label, records)}``."""
    out = {}
    settings = {tuple((k, c["label"][k]) for k in LABEL_KEYS if k != "monitor") for run in runs for c in run.cells()}
    for name, cfg in councils["councils"].items():
        monitors = sorted({cn.parse_member(m)[0] for m in cfg["members"]})
        for setting in sorted(settings):
            member_records, complete = {}, True
            for monitor in monitors:
                try:
                    run, cell = select(runs, {**dict(setting), "monitor": monitor})
                except CompareError:
                    complete = False
                    break
                member_records[monitor] = run.records_of(cell["cell_id"])
            if complete:
                label = {**dict(setting), "monitor": f"council:{name}"}
                out[(name, setting)] = (label, cn.build(cfg["members"], member_records, rule))
    return out


def collected_for(records, pairs):
    return mt.collect(records, pairs)


def best_member(runs, council_cfg, setting, pairs, metric):
    """The member with the best point estimate on ``metric`` (chosen on the same data: conservative for the council)."""
    best, best_value = None, None
    for member in sorted({cn.parse_member(m)[0] for m in council_cfg["members"]}):
        run, cell = select(runs, {**dict(setting), "monitor": member})
        value = mt.point_estimates(mt.collect(run.records_of(cell["cell_id"]), pairs), pairs)["pooled"]["metrics"][metric][0]
        if value is not None and (best_value is None or value > best_value):
            best, best_value = (member, run.records_of(cell["cell_id"])), value
    return best


DEFAULT_FIXED = {"task_context": "none", "hierarchy": "upstream-limits", "partial_cot": "off", "reasoning": "default"}


def run_comparisons(config_path, runs, pairs, councils_path, *, n=2000, seed=0):
    """Run every comparison in ``config_path`` for each value of its ``per`` settings (default: each scope).

    A comparison is ``{id, a, b, per, fixed}`` where ``a`` and ``b`` are partial cell labels (``monitor`` is
    required). Settings not named in ``fixed``, ``per`` or the sides take :data:`DEFAULT_FIXED`. A side can name
    a council (``council:<name>``) or the best single member of one (``best_member_of:<name>``).
    """
    config = tomllib.loads(Path(config_path).read_text())
    councils = cn.load_councils(councils_path)
    metric, told, rule = config.get("metric", "gmean2_clean"), config.get("told", "pooled"), councils["primary_rule"]
    virtual = virtual_cells(runs, councils, rule, None)
    results = []
    for comparison in config["comparisons"]:
        per = comparison.get("per", ["scope"])
        values = sorted({tuple((k, c["label"][k]) for k in per) for run in runs for c in run.cells()})
        for setting in values:
            fixed = {**DEFAULT_FIXED, **comparison.get("fixed", {}), **dict(setting)}
            try:
                a_label, a_records = resolve(runs, virtual, councils, comparison["a"], fixed, pairs, metric)
                b_label, b_records = resolve(runs, virtual, councils, comparison["b"], fixed, pairs, metric)
            except CompareError as error:
                results.append({"id": comparison["id"], "family": dict(setting).get("scope"), "setting": fixed, "skipped": str(error)})
                continue
            ca, cb = mt.collect(a_records, pairs), mt.collect(b_records, pairs)
            if set(ca) != set(cb):
                results.append({"id": comparison["id"], "family": dict(setting).get("scope"), "setting": fixed,
                                "skipped": "the two cells cover different pairs"})
                continue
            note = None
            if any(len(ca[k]) != len(cb[k]) for k in ca):
                ca, cb = mt.collapse_majority(ca), mt.collapse_majority(cb)
                note = "sample counts differ: compared as one majority decision per pair"
            primary = mt.paired_difference(ca, cb, pairs, metric=metric, told=told, n=n, seed=seed)
            recall = mt.paired_difference(ca, cb, pairs, metric="tpr", told=told, n=n, seed=seed)
            results.append({"id": comparison["id"], "family": dict(setting).get("scope"), "setting": fixed,
                            "a": a_label, "b": b_label, "metric": metric, "told": told, "primary": primary,
                            "recall": recall, "outcome": mt.classify_difference(primary, recall), "note": note})
    by_family = {}
    for r in results:
        if "primary" in r:
            by_family.setdefault(r["family"], []).append(r)
    for group in by_family.values():
        adjusted = mt.holm({i: r["primary"]["p_value"] for i, r in enumerate(group)})
        for i, r in enumerate(group):
            r["p_holm"] = adjusted[i]
    return {"metric": metric, "told": told, "bootstrap": {"replicates": n, "seed": seed},
            "holm_family": "all comparisons sharing an observation scope", "results": results}


def _council_match(virtual, name, full):
    matches = [(label, records) for (n, setting), (label, records) in virtual.items()
               if n == name and all(dict(setting).get(k) == v for k, v in full.items() if k in dict(setting))]
    if len(matches) != 1:
        raise CompareError(f"Council {name!r} with settings {full} matches {len(matches)} cells; it must match exactly one")
    return matches[0]


def resolve(runs, virtual, councils, selector, fixed, pairs, metric):
    """``(label, records)`` for a plain selector, a council, or ``best_member_of:<council>``."""
    monitor = selector["monitor"]
    full = {**fixed, **{k: v for k, v in selector.items() if k != "monitor"}}
    if monitor.startswith("council:"):
        return _council_match(virtual, monitor.split(":", 1)[1], full)
    if monitor.startswith("best_member_of:"):
        name = monitor.split(":", 1)[1]
        label, _ = _council_match(virtual, name, full)
        setting = tuple((k, label[k]) for k in LABEL_KEYS if k != "monitor")
        best = best_member(runs, councils["councils"][name], setting, pairs, metric)
        if best is None:
            raise CompareError(f"No member of council {name!r} has a defined {metric}")
        return {**label, "monitor": f"best-member-of-{name}={best[0]}"}, best[1]
    run, cell = select(runs, {**full, "monitor": monitor})
    return cell["label"], run.records_of(cell["cell_id"])
