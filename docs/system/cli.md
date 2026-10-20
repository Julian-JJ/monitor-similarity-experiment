# Command-line tools

All are in `scripts/` and run from the repository root (`.venv/bin/python -B scripts/NAME.py`). `--help` on each lists every option.

| Script | Purpose |
| --- | --- |
| `run_experiment.py` | run or price an experiment file |
| `score_run.py` | compute metrics for a run directory |
| `compare_cells.py` | the pre-registered comparisons over runs |
| `make_report.py` | Markdown report from metrics (and comparisons) |
| `presence_labels.py` | information-presence labelling |
| `freeze.py` | show or write the prompt lock (`status`, `write`) and the presence-rules lock (`rules-status`, `rules-write`) |
| `plan_hierarchy.py` | the original dry-run pricer for one scope and one hierarchy setting (superseded by `run_experiment.py --dry-run` for experiments) |
| `count_transcript_tokens.py` | which single-pass prompts fit a context window |
| `build_objective_table.py`, `build_tool_lists.py` | regenerate `configs/objectives.json` and `configs/tool_lists.json` |
| `download_monitor.py` | download a registered monitor's weights, resolve and record the revision, `--verify-only` ([cluster](cluster.md)) |
| `run_pairs.py` | generate control rollouts, one process per (task, sample) ([cluster](cluster.md)) |
| `build_collection.py` | turn a rollout cache into a verified collection ([collections](collections.md)) |
| `prepare_controls.py` | model directory, derived config, checkout verification and worker plan for the control run ([cluster](cluster.md)) |
| `serve_monitor.py` | serve one registered monitor with vLLM ([cluster](cluster.md)) |
| `pilot_summary.py` | label-free summary of a run for the format-only pilot |
| `generate_rollouts.py`, `serve_model.py`, `download_model.py` | the original actor tooling (not changed) |

## `run_experiment.py`

```bash
run_experiment.py EXPERIMENT.toml [--dry-run] [--monitor NAME] [--set PATH=VALUE ...] [--base-url URL]
                  [--out DIR] [--gpu H200:1] [--job-id ID] [--score] [--bootstrap N] [--timeout S]
                  [--report-tokens N] [--output-json FILE]
```

* `--dry-run` prices without contacting a model; `--output-json` saves the report; `--report-tokens` sets the assumed size of one chunk analysis.
* `--monitor` runs one monitor of a list. `--base-url` is refused with several monitors, because one server serves one model.
* `--gpu H200:1 --job-id $SLURM_JOB_ID` record the compute for GPU-hour reporting.
* `--score` computes `metrics.json` and `metrics.csv` afterwards (needs the rollout files for labels).
* Exit status 2 means some units hit transport errors and will rerun when you run the same command again.

## The rest

```bash
score_run.py runs/NAME [--bootstrap 2000] [--seed 0] [--no-verify]
compare_cells.py runs/NAME [runs/OTHER ...] [--config configs/comparisons.toml] [--councils configs/councils.toml] [--out comparisons.json]
make_report.py runs/NAME/metrics.json [...] [--comparisons comparisons.json] [--title ...] [--out report.md]
freeze.py status | write --status draft|frozen | rules-status | rules-write --status draft|frozen
presence_labels.py [--dir presence] candidates | sample | annotate --annotator NAME [--only-sample] | summarize [--first A --second B]
```
