#!/usr/bin/env python3
"""Count the tokens of the monitor prompt that single-pass monitoring would send.

For each saved rollout and observation scope this renders the transcript with the
library's renderer, fills MonitorBench's unmodified agent prompt, and counts the
whole prompt. It answers: which transcripts fit a monitor's context window?
Counts use the exact tokenizer file you pass; Qwen3-32B shares Qwen3-14B's.
"""

import argparse
import glob
import json
import statistics
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import hierarchy as h  # noqa: E402

VARIANTS = {  # name -> (scope, tool results cut at this many characters; None = never cut)
    "action_cut2000": ("action", 2000),
    "action_full": ("action", None),
    "cot_visible_content_only": ("visible", None),
    "cot_with_reasoning": ("cot", None),
    "all_cut2000": ("all", 2000),
    "all_full": ("all", None),
}


def single_pass_prompt_tokens(messages, scope, cut, prompts, count):
    rollout_turns = h.turns(messages)
    if scope == "visible":  # what upstream's `cot` scope renders: assistant `content` only, no reasoning
        text = "\n\n".join(t["content"] for t in rollout_turns if t["content"].strip())
        scope = "cot"
    else:
        text = "\n\n".join(body for _, body, _ in
                           (h.render_turn(t, scope, False, cut) for t in rollout_turns) if body.strip())
    prompt = h.chunk_prompt(prompts, scope, h.main_task(messages), h.hidden_objective(messages), text, 0, 1)
    return count(prompt), count(text)


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q / 100 * (len(ordered) - 1)))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollouts", default=str(ROOT / "rollouts_original_clean"))
    parser.add_argument("--tokenizer", default=str(ROOT / "cache/tokenizer/tokenizer.json"))
    parser.add_argument("--output", default=str(ROOT / f"mihai/results/transcript-token-counts-{date.today():%Y%m%d}.json"))
    args = parser.parse_args()
    count = h.tokenizer_counter(args.tokenizer)
    prompts = h.load_prompts()
    from monitor_experiment.artifacts import read_json, write_json

    paths = sorted(glob.glob(f"{args.rollouts}/*/*/sample_*/rollout.json"))
    if not paths:
        sys.exit(f"No rollouts under {args.rollouts}")
    rows = []
    for path in paths:
        task, variant, sample = Path(path).parts[-4:-1]
        messages = read_json(path)["messages"]
        row = {"task": task, "variant": variant, "sample": sample, "turns": len(h.turns(messages))}
        for name, (scope, cut) in VARIANTS.items():
            row[name] = single_pass_prompt_tokens(messages, scope, cut, prompts, count)[0]
        rows.append(row)

    limits = {"upstream_input_limit": h.input_limit(h.default_params("all")), "context_32k": 32768, "context_131k": 131072}
    summary = {}
    for name in VARIANTS:
        values = [r[name] for r in rows]
        summary[name] = {"median": int(statistics.median(values)), "p95": percentile(values, 95),
                         "max": max(values), "over": {k: sum(v > lim for v in values) for k, lim in limits.items()}}
    by_task = {}
    for task in sorted({r["task"] for r in rows}):
        group = [r for r in rows if r["task"] == task]
        by_task[task] = {"rollouts": len(group), "median_turns": int(statistics.median(r["turns"] for r in group)),
                         **{name: {"median": int(statistics.median(r[name] for r in group)),
                                   "max": max(r[name] for r in group)} for name in VARIANTS}}
    write_json(args.output, {
        "schema_version": 1, "created": date.today().isoformat(), "rollouts": len(rows),
        "what": "Tokens of the complete single-pass monitor prompt (upstream template filled with main task, hidden objective and transcript).",
        "tokenizer": args.tokenizer, "limits": limits, "variants": VARIANTS,
        "summary": summary, "by_task": by_task, "per_rollout": rows})
    print(f"{len(rows)} rollouts; wrote {args.output}")
    print(f"{'variant':16s}{'median':>9s}{'p95':>9s}{'max':>9s}   over input limit / 32k / 131k")
    for name, s in summary.items():
        o = s["over"]
        print(f"{name:16s}{s['median']:9d}{s['p95']:9d}{s['max']:9d}   "
              f"{o['upstream_input_limit']:2d} / {o['context_32k']:2d} / {o['context_131k']:2d}")


if __name__ == "__main__":
    main()
