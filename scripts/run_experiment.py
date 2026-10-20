#!/usr/bin/env python3
"""Run (or price) an experiment file. See docs/system/cli.md.

  python scripts/run_experiment.py configs/experiments/baseline.toml --dry-run
  python scripts/run_experiment.py configs/experiments/baseline.toml --base-url http://node:8000/v1 --score
  python scripts/run_experiment.py configs/experiments/baseline.toml --set grid.scope=cot --set options.samples=2 --dry-run
"""

import argparse
import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitor_experiment import hierarchy as h  # noqa: E402
from monitor_experiment import runner  # noqa: E402
from monitor_experiment.monitor_client import make_complete  # noqa: E402
from monitor_experiment.registry import Registry  # noqa: E402
from monitor_experiment.spec import load_spec  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment")
    parser.add_argument("--monitor", help="run only this monitor of the experiment's list (one server serves one model)")
    parser.add_argument("--set", action="append", default=[], metavar="PATH=VALUE", help="override a spec value (TOML syntax)")
    parser.add_argument("--dry-run", action="store_true", help="price the experiment without contacting any model")
    parser.add_argument("--out", default=str(ROOT / "runs"), help="runs are written to OUT/<experiment name>/")
    parser.add_argument("--base-url", help="use this server for every monitor (overrides the registry)")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--gpu", help="compute used, e.g. H200:1, recorded for GPU-hour reporting")
    parser.add_argument("--job-id", help="scheduler job id, recorded in the manifest")
    parser.add_argument("--score", action="store_true", help="compute metrics after the run")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--report-tokens", type=int, default=1000, help="dry run: assumed size of one chunk analysis")
    parser.add_argument("--output-json", help="dry run: also write the report here")
    args = parser.parse_args()
    registry = Registry.load()
    spec = load_spec(args.experiment, args.set)
    if args.monitor:
        if args.monitor not in spec.monitors:
            parser.error(f"--monitor {args.monitor!r} is not in this experiment's monitors {list(spec.monitors)}")
        spec = dataclasses.replace(spec, monitors=(args.monitor,))
    if args.base_url and len(spec.monitors) > 1 and not args.dry_run:
        parser.error("--base-url points every monitor at one server, but one server serves one model. Run one monitor per "
                     "invocation with --monitor NAME, or give each monitor its own base_url in configs/monitors.toml.")
    count = h.tokenizer_counter(registry.reference_tokenizer)
    prompts = h.load_prompts()
    if args.dry_run:
        report = runner.dry_run(spec, registry, count=count, prompts=prompts, root=ROOT, report_tokens=args.report_tokens)
        print(runner.format_dry_run(report))
        if args.output_json:
            from monitor_experiment.artifacts import write_json
            write_json(args.output_json, report)
        return
    compute = {}
    if args.gpu:
        kind, _, number = args.gpu.partition(":")
        compute = {"gpu_type": kind, "gpu_count": int(number or 1), "job_id": args.job_id}

    def make(monitor, reasoning):
        client, complete = make_complete(monitor, reasoning, timeout=args.timeout, base_url=args.base_url)
        served = client.check()
        if monitor.model_id.split("/")[-1].lower() not in served["served_model"].lower():
            print(f"WARNING: monitor {monitor.name!r} is {monitor.model_id!r} but the server at {served['base_url']} serves "
                  f"{served['served_model']!r}. Check that the right model is running before trusting this run.", file=sys.stderr)
        return complete, {**served, "monitor": monitor.name, "reasoning": reasoning}
    try:
        run_dir = runner.run_experiment(spec, registry, args.out, make_complete=make, count=count, prompts=prompts,
                                        root=ROOT, compute=compute, spec_path=args.experiment)
    except runner.RunIncomplete as error:
        print("INCOMPLETE:", error, file=sys.stderr)
        sys.exit(2)
    print("run directory:", run_dir)
    if args.score:
        out = runner.score_run(run_dir, registry, bootstrap_n=args.bootstrap)
        print("wrote", run_dir / "metrics.json", "and", run_dir / "metrics.csv")


if __name__ == "__main__":
    main()
