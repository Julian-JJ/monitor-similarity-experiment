# The monitor experiment system: how it works

Status (2026-10-19): **Phase A of [the framework plan](../plan/06-experiment-framework.md) is built and tested offline. Phase B has started on the cluster**: the code is synced, the
environment verified, the format-only pilot has run (Qwen3-14B as monitor; no labels read) and the prompts are frozen, and the `main_only` control rollouts are being generated.
No monitorability result exists yet. See [What is built and what is not](#what-is-built-and-what-is-not) and the [cluster runbook](cluster.md).

## What it does

You write one small TOML file naming a **monitor model**, the **rollout sets** to monitor, and the **variations** to try
(observation scope, task context, reasoning effort, partial CoT, hierarchy settings). One command runs it against a model
server (or only prices it with `--dry-run`); a second computes performance metrics with confidence intervals; a third runs the
pre-registered comparisons; a fourth writes a Markdown report. Everything is read back from stored files, so any step can be
repeated without calling a model again.

```text
configs/experiments/NAME.toml ──► run_experiment.py ──► runs/NAME/{manifest.json, items.jsonl, nodes.jsonl, plans/}
   monitor, rollout sets,            (--dry-run prices it)            │
   variations                                                         ▼
                                       score_run.py (needs the saved labels) ──► metrics.json, metrics.csv
                                                                              │
                      compare_cells.py (P1–P5, councils) ──► comparisons.json │
                                                                              ▼
                                                                  make_report.py ──► report.md
```

## Directory map

| Path | What lives there | Documented in |
| --- | --- | --- |
| `monitor_experiment/data.py` | collections, items, observation vs labels, objective table, pair roles | [data-layer](data-layer.md) |
| `monitor_experiment/registry.py` | monitor and rollout-set registries | [registries](registries.md) |
| `monitor_experiment/spec.py` | experiment files, axes, cells and cell IDs | [experiment-spec](experiment-spec.md) |
| `monitor_experiment/hierarchy.py` | rendering, chunking, prompts, the monitor tree | [hierarchical monitor](../plan/05-hierarchical-monitor.md) |
| `monitor_experiment/strategies.py` | judging strategy, plans (`PlanBook`), partial-CoT transform | [strategies](strategies.md), [plan-context](plan-context.md) |
| `monitor_experiment/monitor_client.py` | talking to a served monitor | [monitor-client](monitor-client.md) |
| `monitor_experiment/runner.py` | running units, resume, dry run, scoring a run | [runner](runner.md), [run-artifacts](run-artifacts.md) |
| `monitor_experiment/metrics.py`, `council.py`, `compare.py` | rates, bootstrap, councils, paired comparisons | [metrics](metrics.md), [comparisons](comparisons.md) |
| `monitor_experiment/costs.py` | cost and latency summaries | [costs](costs.md) |
| `monitor_experiment/report.py` | Markdown reports | [report](report.md) |
| `monitor_experiment/presence.py` | information-presence labels | [presence-labels](presence-labels.md) |
| `monitor_experiment/freeze.py` | fingerprints and the freeze lock | [freeze](freeze.md) |
| `monitor_experiment/collection_builder.py` | turn a rollout cache into a verified collection (for the controls) | [collections](collections.md) |
| `monitor_experiment/control_setup.py`, `monitor_serving.py` | private model directory, derived config, checkout identity; the vLLM command for a monitor | [cluster](cluster.md) |
| `monitor_experiment/pilot.py` | label-free summary of a run for the format-only pilot | [cluster](cluster.md) |
| `monitor_experiment/toollists.py` | the agent's tools, read from source | [plan-context](plan-context.md) |
| `scripts/` | command-line entry points | [cli](cli.md) |
| `mihai/cluster/` | cluster setup, sync, download and job scripts (run: setup, pilot, controls, baseline) | [cluster](cluster.md) |
| `configs/` | registries, experiment files, councils, comparisons, objectives, tool lists, presence rules | each doc above |
| `prompts/`, `vendor/monitorbench_monitor/` | our prompts; MonitorBench's monitor prompt, verbatim | [freeze](freeze.md) |
| `tests/` | 277 offline tests (248 for this system, 29 from the original rollout runner) | [Testing](#testing) |
| `runs/` | outputs of runs (not in Git) | [run-artifacts](run-artifacts.md) |

## The life of one unit

A **unit** is one monitor judgment of one rollout: (cell, rollout, told objective, sample). The runner:

1. **Expands the spec** into cells (the cross product of the variation axes) and units
   (cells × rollouts × told objectives × samples). Each cell has an ID that hashes everything that could change a result.
2. **Skips units already in `items.jsonl`**, so a run resumes where it stopped.
3. **Prepares** the unit (offline): reads the rollout's *observation* (task plus assistant and tool messages, never the system prompt
   or any label), applies the partial-CoT cut if the cell has one, renders the chosen scope, and splits the transcript into chunks that
   fit the monitor's input limit. If the whole transcript fits, there is one chunk and its prompt is MonitorBench's unmodified prompt.
4. **Adds the reference plan** if the cell's task context is `plan`: one of the monitor's own plans for this task, written from the
   main task alone.
5. **Runs the tree**: each chunk is sent to the monitor; the replies are combined in bins of six until one reply remains; its
   `<answer>A|B|C|D</answer>` is the verdict. Retries, invalid answers and truncated replies are handled as described in the
   [hierarchical monitor](../plan/05-hierarchical-monitor.md); invalid is never "not detected".
6. **Writes** one line to `items.jsonl` (the verdict and its cost) and the nodes to `nodes.jsonl`.

Scoring happens later and separately: `score_run` reads the saved labels, assigns every pair a **role** (positive, clean negative,
cross-objective negative, own failure), and computes the metrics. The monitor never sees a label.

## Conventions that hold everywhere

* **Labels are privileged.** A monitor sees an `Observation`; only scoring code asks for `Labels`.
* **Invalid is not negative.** A reply that is truncated or has no A–D answer is `invalid`; it lowers coverage and is left out of rates.
* **Nothing is shortened silently.** Cuts (tool results at 2,000 characters, partial CoT) are explicit, counted and recorded.
* **Deterministic and resumable.** Every ID is a content hash; seeds are derived from the unit; reruns reproduce prompts exactly.
* **Settings that matter are in the cell ID**, including prompt files and the tokenizer, so results are never reused under different settings.
* **Unknowns fail loudly.** Unknown keys, unimplemented axis values, placeholder monitors, missing rollout sets and a violated freeze all stop the run with a message.

## Quickstart (local, no model)

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-analysis.txt
# data needed: rollouts_original_clean/ and cache/tokenizer/tokenizer.json (see the work log for how they were copied)
.venv/bin/python -B -m unittest discover -s tests                   # 277 tests
.venv/bin/python -B scripts/run_experiment.py configs/experiments/baseline.toml --dry-run   # price it
```

## Quickstart (with a served monitor, on the cluster)

```bash
# start one monitor server (one model per server), then:
python scripts/run_experiment.py configs/experiments/baseline.toml --monitor qwen3-32b \
    --base-url http://NODE:8000/v1 --gpu H200:1 --job-id $SLURM_JOB_ID --score
python scripts/compare_cells.py runs/baseline --out comparisons.json
python scripts/make_report.py runs/baseline/metrics.json --comparisons comparisons.json --out report.md
```

## Adding things

| To add | Do this |
| --- | --- |
| a monitor model | add an entry to `configs/monitors.toml` ([registries](registries.md)); name it in an experiment file |
| a rollout set | add an entry to `configs/rollout_sets.toml` with a verified `manifest.json` ([data-layer](data-layer.md)) |
| a value of an existing axis | extend `AXES` in `spec.py` and make the code that reads the axis handle it; add a test |
| a new axis | add it to `AXES`, `_make_cell` and the strategy; it joins the cell ID automatically ([experiment-spec](experiment-spec.md)) |
| a monitor method | write a strategy with `prepare` and `run` returning the same result shape as `hierarchy.run_tree` ([strategies](strategies.md)); metrics and reports need no change |
| a metric | add it in `metrics.metrics_from_tally`, list it in `METRICS`, document it in [metrics](metrics.md) |
| a pre-registered comparison | add a `[[comparisons]]` entry ([comparisons](comparisons.md)); changes after results exist are amendments |

## What is built and what is not

| Built and tested offline | Not built / not done |
| --- | --- |
| data layer, registries, spec and grid, cell IDs | running any monitor model (the client is tested only against a local fake server) |
| hierarchical monitor, plans, partial CoT | the freeze of the presence rules (their lock is `draft`) |
| runner with resume, dry run, concurrency | generating the `main_only` control rollouts, and a script to build their manifest |
| metrics, bootstrap, paired comparisons, Holm | serving other models, downloads, job scripts for monitors |
| councils from stored verdicts | `execute` and `plan_compare` task contexts, follow-up visibility, `structured` prompt |
| cost and latency summaries | interrogation (needs the agent; not planned) |
| report generator | HTML or figures |
| collection builder, control-run helper, monitor-serving command, label-free pilot summary, job scripts | the pilot and the control generation have been **run on the cluster** (results in the work log); the collection builder has not yet been run on real controls |
| presence-label rules, annotation tool, agreement and decomposition | human annotation itself; the frozen rules |

## Testing

`python -B -m unittest discover -s tests` runs 277 tests with no network, GPU or model: 38 for the hierarchical monitor, 17 data,
15 registry and spec, 23 metrics and councils, 10 monitor client (against a real local HTTP server), 5 tool lists, 14 strategies,
24 runner (end to end with fake monitors of known behavior), 9 comparisons, 6 report, 23 presence, 10 freeze, 6 collection builder (against a real generator cache),
11 control setup, 7 monitor serving, 4 pilot summary, 7 cluster-script smoke checks, and the original 23 + 6 for the rollout runner. Tests that need the real 41 rollouts skip themselves if `rollouts_original_clean/` is absent.
The fake monitors (an oracle, an always-detects, a never-detects, and a half-detecting one) make every expected metric
computable by hand, so a wrong formula cannot pass by agreeing with itself.
