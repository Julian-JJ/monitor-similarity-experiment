#!/usr/bin/env python3
"""Dry-run the hierarchical monitor over saved rollouts: chunks, model calls, input tokens.

No model is contacted. Level-0 prompts are built exactly as a real run would
build them, so their token counts are exact. Combining levels depend on what the
monitor writes, so their input is *estimated* from ``--report-tokens``, the
assumed size of one chunk analysis; treat those figures as estimates.
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
from monitor_experiment.artifacts import read_json, write_json  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollouts", default=str(ROOT / "rollouts_original_clean"))
    parser.add_argument("--tokenizer", default=str(ROOT / "cache/tokenizer/tokenizer.json"))
    parser.add_argument("--scopes", nargs="+", default=list(h.SCOPES), choices=h.SCOPES)
    parser.add_argument("--context-tokens", type=int, default=32768)
    parser.add_argument("--output-reserve", type=int, default=16768)
    parser.add_argument("--chunk-tokens", type=int, default=12000)
    parser.add_argument("--bin-size", type=int, default=4)
    parser.add_argument("--no-single-pass-if-fits", action="store_true",
                        help="always chunk at --chunk-tokens, even when the whole prompt fits the input limit")
    parser.add_argument("--samples", type=int, default=4, help="independent monitor samples per rollout (upstream: 4)")
    parser.add_argument("--objectives", type=int, default=1,
                        help="objective disclosures per rollout (2 = each rollout is judged under both the malicious and the benign objective)")
    parser.add_argument("--report-tokens", type=int, default=1000, help="assumed size of one chunk analysis")
    parser.add_argument("--output")
    args = parser.parse_args()
    count = h.tokenizer_counter(args.tokenizer)
    prompts = h.load_prompts()
    paths = sorted(glob.glob(f"{args.rollouts}/*/*/sample_*/rollout.json"))
    if not paths:
        sys.exit(f"No rollouts under {args.rollouts}")
    rows, summary = [], {}
    for scope in args.scopes:
        params = {**h.default_params(scope), "context_tokens": args.context_tokens,
                  "output_reserve": args.output_reserve, "chunk_tokens": args.chunk_tokens,
                  "bin_size": args.bin_size, "single_pass_if_fits": not args.no_single_pass_if_fits}
        for path in paths:
            task, variant, sample = Path(path).parts[-4:-1]
            messages = read_json(path)["messages"]
            planned = h.plan(messages, params, count, prompts)
            n = len(planned["chunks"])
            calls, levels = h.estimate_tree(n, args.bin_size)
            level0 = sum(c["prompt_tokens"] for c in planned["chunks"])
            overhead = count(h.reduce_prompt(prompts, planned["main_task"], planned["objective"], [(1, 1, "")]))
            rows.append({"scope": scope, "task": task, "variant": variant, "sample": sample,
                         "turns": planned["turn_count"], "chunks": n, "levels": levels,
                         "calls_per_sample": calls, "hierarchical": planned["hierarchical"],
                         "truncated_tool_results": planned["truncated_tool_results"],
                         "max_chunk_prompt_tokens": max(c["prompt_tokens"] for c in planned["chunks"]),
                         "level0_input_tokens": level0,
                         "input_tokens_per_sample_estimate": h.estimate_tree_tokens(level0, n, params["bin_size"], args.report_tokens, overhead)})
        group = [r for r in rows if r["scope"] == scope]
        summary[scope] = {
            "rollouts": len(group),
            "single_chunk": sum(not r["hierarchical"] for r in group),
            "hierarchical": sum(r["hierarchical"] for r in group),
            "chunks_median": int(statistics.median(r["chunks"] for r in group)),
            "chunks_max": max(r["chunks"] for r in group),
            "levels_max": max(r["levels"] for r in group),
            "calls_per_sample_total": sum(r["calls_per_sample"] for r in group),
            "model_calls_total_all_samples": sum(r["calls_per_sample"] for r in group) * args.samples * args.objectives,
            "input_tokens_total_all_samples_estimate": sum(r["input_tokens_per_sample_estimate"] for r in group) * args.samples * args.objectives,
            "truncated_tool_results_total": sum(r["truncated_tool_results"] for r in group)}
    settings = {"context_tokens": args.context_tokens, "output_reserve": args.output_reserve,
                "chunk_tokens": args.chunk_tokens, "bin_size": args.bin_size, "samples": args.samples,
                "objectives": args.objectives, "assumed_report_tokens": args.report_tokens, "input_limit": h.input_limit(params),
                "single_pass_if_fits": not args.no_single_pass_if_fits}
    print(f"settings: {settings}")
    print(f"{'scope':7s}{'single':>8s}{'hier.':>7s}{'chunks med/max':>16s}{'levels':>8s}{'calls/sample':>14s}{'calls x samples':>17s}{'input tokens (est.)':>22s}")
    for scope, s in summary.items():
        print(f"{scope:7s}{s['single_chunk']:8d}{s['hierarchical']:7d}{s['chunks_median']:>9d}/{s['chunks_max']:<5d}{s['levels_max']:8d}"
              f"{s['calls_per_sample_total']:14d}{s['model_calls_total_all_samples']:17d}{s['input_tokens_total_all_samples_estimate']:22,d}")
    if args.output:
        write_json(args.output, {"schema_version": 1, "created": date.today().isoformat(),
                                 "settings": settings, "summary": summary, "per_rollout": rows})
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
