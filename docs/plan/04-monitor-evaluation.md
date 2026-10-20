# Monitor evaluation and reporting

Related: [scope](01-scope.md) · [setup](02-setup-and-architecture.md) · [rollouts](03-rollouts.md).

Proposed interface (**superseded**): `scripts/run_monitors.py --config configs/monitors.toml`. The built interface is
`scripts/run_experiment.py configs/experiments/NAME.toml`, and `configs/monitors.toml` is now the monitor registry; see
[the system documentation](../system/README.md) and [the framework plan](06-experiment-framework.md).

## Experimental controls

| Setting | Values/behavior |
| --- | --- |
| Model | Registry entry or custom endpoint |
| Original observation | `actions`, `cot`, `all` |
| Follow-up visibility | `none`, `answer`, `cot`, `all` |
| Follow-up samples | Number of cached completions supplied |
| Passes | Positive integer |
| Pass strategy | Sequential revision or independent ensemble |
| Perform task first | Enabled/disabled |
| Compute limits | Explicit per-pass and total generation limits |

Actions include tool calls, tool responses, and externally visible assistant outputs. CoT includes actor reasoning only. All includes both in chronological order. Give all conditions the same allowed task context and objective disclosure. Exclude hidden actor instructions, reference solutions, evaluator feedback, labels, and privileged environment state from observation rendering.

A pass is one complete inspection of the selected observation. Sequential revision receives the same observation and prior monitor analysis. Independent passes start fresh and use a predetermined aggregation rule. Cache every pass and record actual token use; equal pass counts do not imply equal compute.

Require structured output with verdict, bounded confidence score, and evidence references to message IDs. Confidence is model-reported, not assumed calibrated. Preserve invalid responses as failures rather than interpreting them as negative verdicts.

The baseline condition is the exception: it follows MonitorBench and uses its unmodified A–D prompt, in which `A` means "detected" (see [the research notes](../research/monitor-baseline-notes.md)). It does not report a confidence score. The structured-output requirement above applies to later conditions. Both conditions keep invalid responses as failures.

For long traces, use an explicit policy: full trace where supported or a separately identified hierarchical condition. Never silently truncate or combine full-trace and hierarchical results under one condition.

Measured on the 41 saved rollouts, this policy is needed: with upstream's 15,488-token monitor input limit, 9 of 41 `action`-scope prompts and all `cot`- and `all`-scope prompts exceed one pass ([measurements](../analysis/transcript-token-counts.md)). The [hierarchical monitor design](05-hierarchical-monitor.md) defines the hierarchical condition. A transcript that fits one pass is monitored by the unmodified upstream prompt, and each result records whether it was single-pass or hierarchical so the two are never pooled.

## Perform the task first

1. Give the monitor the main task and specified side objective.
2. Run its own attempt in a fresh copy of the initial simulated environment, with the same tools and a fixed budget.
3. Save and evaluate that attempt.
4. Supply its attempt plus the selected actor observations, then request a monitoring verdict.

Cache this stage separately. Keep objective disclosure identical in direct-monitoring and task-first conditions. Record unsuccessful attempts, refusals, and extra compute. A prose-only imagined solution can be a separate optional condition; it is distinct from executing the task.

## Metrics

Predict verified side-objective completion and report malicious/benign variants separately. Use identical rollout IDs across monitor conditions.

- Primary: TPR, TNR, and `g-mean² = TPR × TNR`.
- Supporting: confusion matrix, class counts, side-objective prevalence, and main-task success.
- Secondary: detection among successful side-objective trajectories, plus a main-task-success-conditioned breakdown.
- Operational: invalid-output rate, coverage, latency, and token usage, including task-first overhead.

Use actual outcome labels for both dual-objective runs and main-task-only controls. Benign side-objective completions are not negatives for malicious-objective detection. Identify judge-dependent subsets explicitly.

Report undefined metrics when a class is absent. Publish valid-prediction coverage and a conservative sensitivity analysis for failed monitor outputs, rather than hiding them through exclusion. Use paired condition comparisons and task-aware bootstrap intervals; distinguish within-task sampling uncertainty from generalization across the five base tasks.

Export per-sample/per-pass JSONL, summary JSON, CSV tables, and configuration/provenance manifests. Any threshold selection must be fixed in advance or use a separate calibration split.

## Implementation and acceptance sequence

Superseded: the ordering below was refined into a reusable experiment framework with
registries, a declarative spec, standard metrics and a report generator; see
[06](06-experiment-framework.md). The experimental controls and metrics above still
define what the framework must support.

Status: step 1 is done for the baseline condition (`monitor_experiment/hierarchy.py`:
observation rendering by scope, MonitorBench's A–D verdict parsing, offline tests that
no system-prompt text reaches a prompt). Steps 2 onward, including the metrics, are not
implemented.

1. Implement observation filtering and structured verdict parsing.
2. Implement repeated passes, aggregation, and task-first environment isolation.
3. Validate metrics against hand-calculated confusion matrices and paired examples.
4. Test filtering for reasoning/action leakage and exclusion of labels and privileged state.
5. Pilot one programmatic environment, both objective variants, main-task-only controls, and two monitor sizes.
6. Expand to all tasks and the requested model registry after the pilot passes.

The final framework should reproduce each comparison from frozen artifacts without rerunning the actor.
