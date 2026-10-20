# Reports

Code: [`monitor_experiment/report.py`](../../monitor_experiment/report.py); entry point `scripts/make_report.py`. Tests: `tests/test_report.py`.

`render(metrics_paths, comparisons_path=None, title=...)` turns one or more `metrics.json` files (and optionally a `comparisons.json`) into Markdown. It reads
only stored results: it never contacts a model and can be rerun at any time. Values are shown as `value [95% interval]`; an undefined value is `n/a`.

## Sections

1. **Header.** The runs, their rollout sets and how many rollouts each used, samples per pair, bootstrap settings, and whether prompts were frozen.
2. **Caveats**, written automatically from the data (see below).
3. **Settings.** One row per cell: monitor, relation to the fixed agent, scope, context, hierarchy, units found/expected, whether complete.
4. **Headline metrics**, three tables (both told objectives pooled; told the malicious objective; told the benign objective): TPR (the MonitorBench score), TNR (clean),
   g-mean² (clean), coverage.
5. **Secondary: objective-specificity**, with cross-objective negatives (impure) and own-objective failures.
6. **Sample sizes.** Pairs per role for each cell.
7. **Cost and latency.** Units, calls, requests, tokens, served seconds, per-call latency, critical path per cell; then compute (job wall time and GPU-hours) **per monitor**, not per cell.

Caveats now also name any session whose commit was not recorded or whose tree was dirty (per session, from `metrics.json`).
8. **Pre-registered comparisons**, when `comparisons.json` is given: outcome, difference, interval, p and Holm-adjusted p, skipped ones with reasons, notes.

## Automatic caveats

The report states, whenever it applies: prompts not frozen (the run is a pilot, not confirmatory); a run made from an uncommitted working tree;
incomplete cells; no clean negatives at all (so TNR and g-mean² are undefined and only recall can be read); cells that used the hierarchical monitor
(separate conditions, not pooled); fewer than 90% valid verdicts; fewer than 30 positive pairs; and always, that the three tasks are held fixed in the bootstrap and
that cross-objective negatives are impure. Caveats cannot be removed by an option.

## Not included

No figures and no HTML yet; `metrics.csv` is tidy so any plotting can start from one file. Comparisons across runs with different settings are the reader's to
state; the pre-registered ones are in `configs/comparisons.toml`.


## Reports produced so far

`reports/baseline.md`: Qwen3-32B, no task context, three scopes, 75 rollouts (`python scripts/make_report.py runs/baseline/metrics.json --title "Baseline: Qwen3-32B, no task context" --out reports/baseline.md`). It carries the dirty-tree caveat. `runs/` is git-ignored; `reports/` is not.
