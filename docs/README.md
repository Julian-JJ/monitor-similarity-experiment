# Documentation index

| Document | What it is |
| --- | --- |
| [Repository README](../README.md) | what is implemented, how to run it |
| [Cluster guide](../mihai/README.md) | Bouchet locations, installed software, saved data, local copy |
| [Work log](worklog.md) | chronological record of what was done, including mistakes and declined actions |
| [Scope](plan/01-scope.md) · [Setup](plan/02-setup-and-architecture.md) · [Rollouts](plan/03-rollouts.md) · [Monitor evaluation](plan/04-monitor-evaluation.md) | the intended framework |
| [Experiment framework](plan/06-experiment-framework.md) | **plan, not built**: one spec to choose a monitor and variations, run, and get metrics and a report; supersedes the older step list |
| [Design decisions](plan/07-design-decisions.md) | choices fixed before any results: monitor pool, councils and voting rules, plans per task, the information-presence label protocol, confirmatory comparisons, compute stance, amendment log |
| [Hierarchical monitor](plan/05-hierarchical-monitor.md) | design of the monitor for transcripts too long for one prompt; status and open decisions |
| [Transcript token counts](analysis/transcript-token-counts.md) | measurements: which prompts fit a context window; dry-run plan and cost |
| [Baseline research notes](research/monitor-baseline-notes.md) | what MonitorBench's code and the two papers do; reliability of each source; what is not established |
| [Evaluator notes](evaluator-notes.md) | differences between the paper's task checks and the vendored code |
| [Rollout format](rollout-format.md) | the saved artifact schema |

## Status at a glance (2026-10-19)

| Item | State |
| --- | --- |
| Actor rollouts and follow-ups (Qwen3-14B, 3 tasks) | done; 41 clean pairs on the cluster |
| Hierarchical monitor library, prompts, offline tests | done; 30 tests pass |
| Token counts and dry-run plans over the 41 rollouts | done; results in `mihai/results/` |
| Running any monitor model | **not done** |
| `scripts/run_monitors.py`, metrics (TPR, TNR, g-mean², bootstrap) | **not written** |
| `main_only` control rollouts (clean negatives) | **planned, not generated**: spec in [07](plan/07-design-decisions.md#211-control-rollouts) (about 30, needs one H200 job) |
| Design decisions pre-registered (monitor pool, councils, hierarchy settings, prompts' design, presence-label protocol) | done in [07](plan/07-design-decisions.md); **uncommitted**, so not yet dated |
| Prompt files for plan context, `prompts.lock.json`, presence rules, annotation tool | **not written** |
| Follow-up visibility in monitor input | **not implemented** |

## Changed in the repository on 2026-10-19

New files are listed in the [work log](worklog.md#files-created). Edits to existing files:

| File | Change | Why |
| --- | --- | --- |
| `README.md` | status text, a "Monitor planning and local analysis" section, link to this index | the old text said hierarchical aggregation was only planned |
| `docs/plan/01-scope.md` | status line; reading guide gains item 5 and links | match the new documents |
| `docs/plan/02-setup-and-architecture.md` | `run_monitors.py` marked not yet written; the two helper scripts and `hierarchy.py` named | the table implied only three entry points |
| `docs/plan/04-monitor-evaluation.md` | measured need for a hierarchical condition; baseline uses upstream's A–D prompt; implementation status | reconcile the structured-output requirement with the baseline |
| `docs/rollout-format.md` | renderer now exists; says what it reads | the text said "future" renderers |
| `docs/plan/04-monitor-evaluation.md` | pointer to the experiment-framework plan (added later the same day) | the implementation sequence there is superseded |
| `vendor/README.md` | points to the new `monitorbench_monitor/` subset | new vendored files |
| `mihai/README.md` | local copy, tracked results, accurate status of monitor code | the old text said no monitor code existed |
| `monitor_experiment/__init__.py` | docstring mentions the monitor library | accuracy |
