# Documentation index

| Document | What it is |
| --- | --- |
| [Repository README](../README.md) · [Rollout runner guide](rollout-runner-guide.md) | project overview and progress; the previous README (rollout generation, cache, tests) |
| [Cluster guide](../mihai/README.md) | Bouchet locations, installed software, saved data, local copy |
| [Work log](worklog.md) | chronological record of what was done, including mistakes and declined actions |
| [Scope](plan/01-scope.md) · [Setup](plan/02-setup-and-architecture.md) · [Rollouts](plan/03-rollouts.md) · [Monitor evaluation](plan/04-monitor-evaluation.md) | the intended framework |
| **[System documentation](system/README.md)** | **how the built system works**: architecture, every module, file formats, metrics, commands, how to add things |
| [Cluster runbook](system/cluster.md) · [Collections](system/collections.md) | Phase B: the scripts for the control rollouts, serving monitors and the pilot, and what is and is not verified |
| [Experiment framework](plan/06-experiment-framework.md) | the plan behind it; Phase A is built (status table inside), Phases B and C are not |
| [Design decisions](plan/07-design-decisions.md) | choices fixed before any results: monitor pool, councils and voting rules, plans per task, the information-presence label protocol, confirmatory comparisons, compute stance, amendment log |
| [Hierarchical monitor](plan/05-hierarchical-monitor.md) | design of the monitor for transcripts too long for one prompt; status and open decisions |
| [Transcript token counts](analysis/transcript-token-counts.md) | measurements: which prompts fit a context window; dry-run plan and cost |
| [Baseline results](analysis/baseline-results.md) | Qwen3-32B baseline: what ran, metrics, per-task and per-told breakdown, confounds |
| [Baseline research notes](research/monitor-baseline-notes.md) | what MonitorBench's code and the two papers do; reliability of each source; what is not established |
| [Evaluator notes](evaluator-notes.md) | differences between the paper's task checks and the vendored code |
| [Rollout format](rollout-format.md) | the saved artifact schema |

## Status at a glance (2026-10-19)

| Item | State |
| --- | --- |
| Actor rollouts and follow-ups (Qwen3-14B, 3 tasks) | done; 41 clean pairs on the cluster |
| Hierarchical monitor library, experiment framework (data, registries, spec, runner, metrics, comparisons, report, presence tooling), prompts | done; 281 offline tests pass (252 new) |
| Token counts and dry-run plans over the 41 rollouts | done; results in `mihai/results/` |
| Running any monitor model | pilot (Qwen3-14B, format-only, no labels read) and the **baselines** (Qwen3-32B and Qwen3-14B, 1,800 units each, scored; `reports/baseline.md`, [analysis](analysis/baseline-results.md)); first comparison P1b run (no clear difference); no other monitor yet |
| Metrics (TPR, TNR, g-mean², bootstrap), comparisons, councils, report | done and tested against hand-worked numbers |
| `scripts/run_experiment.py` (run and price experiments) | done; exercised only with fake monitors and a local fake server |
| `main_only` control rollouts (clean negatives) | **done**: 34 pairs kept of 36 (job 30068222), collection `main_only_v1` built and verified ([cluster runbook](system/cluster.md)) |
| Design decisions pre-registered (monitor pool, councils, hierarchy settings, prompts' design, presence-label protocol) | done in [07](plan/07-design-decisions.md); **committed in `392288e`** on branch `monitor-framework` (not pushed), which dates it. Code written after that commit is uncommitted |
| Format-only pilot (Qwen3-14B as monitor, 48 units) | **done on the cluster** (job 30068179): 352 requests, none invalid, truncated or retried; details in the work log |
| Prompt lock | **`frozen`** after the pilot; presence rules (v0.2) stay `draft` under their own lock until the annotator agreement check |
| Control rollouts | **done** (job 30068222; job 30068171 was cancelled after a design flaw), see the work log |
| Follow-up visibility in monitor input | **not implemented** |

## Changed in the repository on 2026-10-19

New files are listed in the work log ([part 1](worklog.md#files-created-part-1), [part 2](worklog.md#files-created-part-2)); the system documentation is under [`system/`](system/README.md). Edits to existing files:

| File | Change | Why |
| --- | --- | --- |
| `README.md` | status text, a "Monitor planning and local analysis" section, link to this index | the old text said hierarchical aggregation was only planned |
| `docs/plan/01-scope.md` | status line; reading guide gains item 5 and links | match the new documents |
| `docs/plan/02-setup-and-architecture.md` | `run_monitors.py` replaced by `run_experiment.py` and its companions (built) | the table implied only three entry points, one of them never built under that name |
| `docs/plan/04-monitor-evaluation.md` | measured need for a hierarchical condition; baseline uses upstream's A–D prompt; implementation status; the proposed `run_monitors.py --config configs/monitors.toml` marked superseded | `configs/monitors.toml` is now the monitor registry |
| `docs/rollout-format.md` | renderer now exists; says what it reads | the text said "future" renderers |
| `docs/plan/04-monitor-evaluation.md` | pointer to the experiment-framework plan (added later the same day) | the implementation sequence there is superseded |
| `vendor/README.md` | points to the new `monitorbench_monitor/` subset | new vendored files |
| `mihai/README.md` | local copy, tracked results, the monitor section rewritten to describe the built runner | the old text said no monitor code existed |
| `docs/plan/05-hierarchical-monitor.md`, `06-experiment-framework.md`, `07-design-decisions.md` | status lines, test counts, Phase A status table, measured dry-run costs, presence-annotation effort | they described the library alone, or a plan not yet built |
| `README.md` | the monitor section now lists the built commands and the real test count | |
| `monitor_experiment/__init__.py` | docstring mentions the monitor library | accuracy |
