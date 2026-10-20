#!/usr/bin/env python3
"""Information-presence labelling: propose spans, collect human answers, check agreement, write labels.

  candidates   rule-proposed evidence spans for every positive pair        -> presence/candidates.json
  sample       a stratified sample of pairs for two annotators to double-label, and a spot-check sample
  annotate     interactive: you answer y / n / u for each span (run once per annotator)
  summarize    agreement (Cohen's kappa), spot-check recall of the rules, and the pair labels

See docs/system/presence-labels.md for the protocol and docs/plan/07-design-decisions.md 2.5 for why.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import hierarchy as h  # noqa: E402
from monitor_experiment import presence as pr  # noqa: E402
from monitor_experiment.artifacts import read_json, write_json  # noqa: E402
from monitor_experiment.registry import Registry  # noqa: E402

DEFAULT_DIR = ROOT / "presence"


def load_candidates(path):
    data = read_json(path)
    return {(c["item_id"], c["objective"]): c["spans"] for c in data["candidates"]}


def read_lines(path):
    path = Path(path)
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.is_file() else []


def cmd_candidates(args):
    registry = Registry.load()
    items = registry.load_set(args.rollout_set).items
    rules = pr.load_rules()
    found = pr.candidates_for(items, rules)
    write_json(Path(args.dir) / "candidates.json", {
        "schema_version": 1, "rules_version": rules["version"], "rules_status": rules["status"], "rollout_set": args.rollout_set,
        "candidates": [{"item_id": i, "objective": o, "spans": s} for (i, o), s in sorted(found.items())]})
    print(f"{len(found)} positive pairs, {sum(len(s) for s in found.values())} candidate spans -> {Path(args.dir) / 'candidates.json'}")


def cmd_sample(args):
    cands = load_candidates(Path(args.dir) / "candidates.json")
    registry = Registry.load()
    by_id = {i.item_id: i for i in registry.load_set(json.loads((Path(args.dir) / "candidates.json").read_text())["rollout_set"]).items}
    double = pr.stratified_sample(list(cands), args.pairs, args.seed)
    spot_pool = [k for k in cands if k not in set(double)]
    spot = pr.spot_check_sample(spot_pool, lambda item_id: h.turns(by_id[item_id].raw()["messages"]), args.spot_pairs, args.spot_turns, args.seed)
    write_json(Path(args.dir) / "sample.json", {"seed": args.seed, "double_annotated": [list(k) for k in double], "spot_check": spot})
    print(f"{len(double)} pairs for double annotation; {len(spot)} turns for the spot check -> {Path(args.dir) / 'sample.json'}")


def cmd_annotate(args):
    cands = load_candidates(Path(args.dir) / "candidates.json")
    out = Path(args.dir) / "annotations.jsonl"
    existing = read_lines(out)
    keys = None
    if args.only_sample:
        keys = [tuple(k) for k in read_json(Path(args.dir) / "sample.json")["double_annotated"]]
    todo = pr.pending(cands, existing, args.annotator, keys)
    print(f"{len(todo)} spans to answer as {args.annotator!r}. Answers are saved as you go; q quits.")

    def save(record):
        with out.open("a") as stream:
            stream.write(json.dumps(record) + "\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    pr.annotate(todo, args.annotator, input, print, save)


def cmd_summarize(args):
    directory = Path(args.dir)
    cands = load_candidates(directory / "candidates.json")
    annotations = read_lines(directory / "annotations.jsonl")
    labels = pr.pair_labels(cands, annotations)
    counts = {}
    for states in labels.values():
        for source in ("reasoning", "actions"):
            counts.setdefault(source, {}).setdefault(states[source], 0)
            counts[source][states[source]] += 1
    summary = {"pairs": len(labels), "label_counts": counts}
    if args.first and args.second:
        summary["kappa"] = pr.annotator_kappa(annotations, args.first, args.second)
    spots = read_lines(directory / "spot_check.jsonl")
    if spots:
        summary["spot_check"] = pr.spot_check_recall(spots, cands)
    write_json(directory / "labels.json", {"summary": summary, "labels": [
        {"item_id": i, "objective": o, **states} for (i, o), states in sorted(labels.items())]})
    print(json.dumps(summary, indent=2))
    print("thresholds (docs/plan/07 2.5): kappa >= 0.7 and spot-check recall >= 0.9 before the labels are used")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="where candidates, sample and annotations live")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("--rollout-set", default="original_clean")
    s = sub.add_parser("sample")
    s.add_argument("--pairs", type=int, default=20)
    s.add_argument("--spot-pairs", type=int, default=6)
    s.add_argument("--spot-turns", type=int, default=10)
    s.add_argument("--seed", type=int, default=0)
    a = sub.add_parser("annotate")
    a.add_argument("--annotator", required=True)
    a.add_argument("--only-sample", action="store_true", help="only the double-annotated sample")
    m = sub.add_parser("summarize")
    m.add_argument("--first")
    m.add_argument("--second")
    args = parser.parse_args()
    {"candidates": cmd_candidates, "sample": cmd_sample, "annotate": cmd_annotate, "summarize": cmd_summarize}[args.command](args)


if __name__ == "__main__":
    main()
