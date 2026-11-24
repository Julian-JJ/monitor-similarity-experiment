# Baselines: Qwen3-32B and Qwen3-14B, no task context

Runs: `baseline`. Generated from stored results only; no model was contacted.

* `baseline`: rollout sets original_clean: 41 rollouts, main_only_v1: 34 rollouts; 4 monitor samples per pair; bootstrap 2000 replicates (seed 0); prompts frozen.

## Caveats

* Run `baseline`: the commit used by job 30068483 was not recorded (it ran before sessions recorded their own commit; the manifest keeps only the latest invocation's: 8d8979fe17, dirty: False). Check the work log.
* Run `baseline`: the commit used by job 30069109 was not recorded (it ran before sessions recorded their own commit; the manifest keeps only the latest invocation's: 8d8979fe17, dirty: False). Check the work log.
* Run `baseline`: the commit used by job 30069778 was not recorded (it ran before sessions recorded their own commit; the manifest keeps only the latest invocation's: 8d8979fe17, dirty: False). Check the work log.
* Some cells used the hierarchical monitor and are separate conditions from single-pass monitoring; they are not pooled: qwen3-32b · action · context none (120 of 600 units); qwen3-32b · cot · context none (600 of 600 units); qwen3-32b · all · context none (600 of 600 units); qwen3-14b · action · context none (120 of 600 units); qwen3-14b · cot · context none (600 of 600 units); qwen3-14b · all · context none (600 of 600 units).
* The three tasks are held fixed in the bootstrap: intervals describe variability of rollouts and monitor samples within these tasks, not generalization to new tasks. Conclusions are preliminary.
* Cross-objective negatives (rollouts whose agent pursued the *other* objective) are impure: the judge prompt's option A is worded generally. They are shown separately as objective-specificity and are not pooled with clean negatives.

## Settings

| monitor | relation to the agent | scope | context | hierarchy | units | complete |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3-32b | same_family_larger | action | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | cot | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | all | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | action | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | cot | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | all | none | upstream-limits | 600/600 | yes |

## Both told objectives pooled

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.712 [0.636, 0.784] | 0.712 [0.636, 0.784] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.951 [0.886, 1.000] | 0.784 [0.728, 0.843] | 0.746 [0.678, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.945 [0.881, 1.000] | 0.758 [0.697, 0.814] | 0.716 [0.641, 0.788] | 1.000 [1.000, 1.000] |
| qwen3-14b · action · context none | 0.970 [0.921, 1.000] | 0.792 [0.723, 0.859] | 0.768 [0.692, 0.842] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.963 [0.917, 1.000] | 0.837 [0.784, 0.890] | 0.806 [0.739, 0.872] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 0.976 [0.933, 1.000] | 0.795 [0.739, 0.854] | 0.776 [0.716, 0.835] | 1.000 [1.000, 1.000] |

## Told the malicious objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.530 [0.432, 0.636] | 0.530 [0.432, 0.636] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 1.000 [1.000, 1.000] | 0.636 [0.530, 0.750] | 0.636 [0.530, 0.750] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.989 [0.957, 1.000] | 0.606 [0.508, 0.699] | 0.599 [0.502, 0.695] | 1.000 [1.000, 1.000] |
| qwen3-14b · action · context none | 1.000 [1.000, 1.000] | 0.636 [0.516, 0.757] | 0.636 [0.516, 0.757] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.966 [0.896, 1.000] | 0.758 [0.654, 0.856] | 0.732 [0.635, 0.831] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 1.000 [1.000, 1.000] | 0.682 [0.576, 0.787] | 0.682 [0.576, 0.787] | 1.000 [1.000, 1.000] |

## Told the benign objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.894 [0.809, 0.970] | 0.894 [0.809, 0.970] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.895 [0.773, 1.000] | 0.932 [0.858, 0.985] | 0.834 [0.703, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.895 [0.773, 1.000] | 0.909 [0.826, 0.978] | 0.813 [0.682, 0.941] | 1.000 [1.000, 1.000] |
| qwen3-14b · action · context none | 0.934 [0.841, 1.000] | 0.947 [0.875, 1.000] | 0.885 [0.778, 0.979] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.961 [0.893, 1.000] | 0.917 [0.846, 0.977] | 0.880 [0.794, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 0.947 [0.861, 1.000] | 0.909 [0.839, 0.969] | 0.861 [0.764, 0.941] | 1.000 [1.000, 1.000] |

## Secondary: objective-specificity (cross-objective negatives)

Impure negatives: see the caveats. Pooled over both told objectives.

| cell | TNR (cross-objective) | g-mean² (cross-objective) | TNR (own failures) |
| --- | --- | --- | --- |
| qwen3-32b · action · context none | 0.662 [0.581, 0.732] | 0.662 [0.581, 0.732] | 0.000 [0.000, 0.000] |
| qwen3-32b · cot · context none | 0.738 [0.650, 0.817] | 0.702 [0.612, 0.787] | 0.000 [0.000, 0.000] |
| qwen3-32b · all · context none | 0.806 [0.732, 0.875] | 0.762 [0.680, 0.842] | 0.000 [0.000, 0.000] |
| qwen3-14b · action · context none | 0.706 [0.616, 0.795] | 0.685 [0.598, 0.771] | 0.000 [0.000, 0.000] |
| qwen3-14b · cot · context none | 0.750 [0.659, 0.841] | 0.723 [0.634, 0.815] | 0.000 [0.000, 0.000] |
| qwen3-14b · all · context none | 0.675 [0.590, 0.756] | 0.659 [0.570, 0.747] | 0.000 [0.000, 0.000] |

## Sample sizes (pooled, pairs)

| cell | positive | clean negative | cross-objective | own failures |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 41 | 66 | 40 | 3 |
| qwen3-32b · cot · context none | 41 | 66 | 40 | 3 |
| qwen3-32b · all · context none | 41 | 66 | 40 | 3 |
| qwen3-14b · action · context none | 41 | 66 | 40 | 3 |
| qwen3-14b · cot · context none | 41 | 66 | 40 | 3 |
| qwen3-14b · all · context none | 41 | 66 | 40 | 3 |

## Cost and latency

Tokens are as the server counted them. `served s` is the sum of request latencies (load, not GPU occupancy). `critical path` is the per-unit wall time if each tree level ran in parallel. Compute is per monitor, below, because a job is shared by the cells it runs.

| cell | units | calls | requests | prompt tokens | completion tokens | served s | call latency p50/p95 s | critical path mean s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 600 | 856 | 856 | 7,100,445 | 972,709 | 41792 | 41.1/101.4 | 61.9 |
| qwen3-32b · cot · context none | 600 | 6352 | 6353 | 57,383,449 | 6,192,523 | 306981 | 47.4/77.5 | 137.7 |
| qwen3-32b · all · context none | 600 | 7008 | 7010 | 63,820,612 | 6,354,269 | 317810 | 43.7/72.4 | 135.4 |
| qwen3-14b · action · context none | 600 | 856 | 856 | 7,098,737 | 1,093,931 | 24928 | 22.9/63.9 | 37.3 |
| qwen3-14b · cot · context none | 600 | 6352 | 6352 | 57,177,327 | 6,078,724 | 154604 | 23.1/39.0 | 73.1 |
| qwen3-14b · all · context none | 600 | 7008 | 7009 | 63,648,054 | 6,526,819 | 166191 | 22.1/39.0 | 76.8 |

Compute per monitor: job wall time of the sessions that ran only that monitor, times the GPU count. It includes server start-up and idle time inside the job.

| run | monitor | jobs | GPU | wall time (h) | GPU-hours |
| --- | --- | --- | --- | --- | --- |
| baseline | qwen3-32b | 30068483, 30069109 | H200 | 5.84 | 5.84 |
| baseline | qwen3-14b | 30069778 | H200 | 3.01 | 3.01 |

## Pre-registered comparisons (primary metric `gmean2_clean`, told: pooled)

Difference = first minus second, with a paired bootstrap interval over rollouts. Holm adjustment within each observation scope. 2000 replicates, seed 0. `mixed` means the primary metric and recall point in opposite directions, and no win is claimed.

| comparison | scope | outcome | difference | interval | p | p (Holm) |
| --- | --- | --- | --- | --- | --- | --- |
| P1a same-model vs smaller (qwen3-4b) | action | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P1a same-model vs smaller (qwen3-4b) | all | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P1a same-model vs smaller (qwen3-4b) | cot | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P1b same-model vs larger (qwen3-32b) | action | no clear difference | +0.055 | [-0.006, +0.120] | 0.077 | 0.077 |
| P1b same-model vs larger (qwen3-32b) | all | no clear difference | +0.060 | [-0.011, +0.132] | 0.103 | 0.103 |
| P1b same-model vs larger (qwen3-32b) | cot | no clear difference | +0.061 | [-0.016, +0.140] | 0.130 | 0.130 |
| P2 dense vs mixture-of-experts (qwen3-32b vs qwen3-30b-a3b) | action | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P2 dense vs mixture-of-experts (qwen3-32b vs qwen3-30b-a3b) | all | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P2 dense vs mixture-of-experts (qwen3-32b vs qwen3-30b-a3b) | cot | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P3a qwen3-32b vs gpt-oss-120b | action | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P3a qwen3-32b vs gpt-oss-120b | all | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P3a qwen3-32b vs gpt-oss-120b | cot | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P3b qwen3-32b vs gemma-large | action | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P3b qwen3-32b vs gemma-large | all | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P3b qwen3-32b vs gemma-large | cot | skipped | Selector {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-14b) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-14b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-14b) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-14b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-14b) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-14b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-4b) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-4b) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-4b) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-4b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-32b) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-32b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-32b) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-32b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-32b) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-32b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-30b-a3b) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-30b-a3b) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (qwen3-30b-a3b) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'qwen3-30b-a3b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gpt-oss-120b) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gpt-oss-120b) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gpt-oss-120b) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'gpt-oss-120b'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gemma-large) | action | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gemma-large) | all | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P4 plan vs none (gemma-large) | cot | skipped | Selector {'task_context': 'plan', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot', 'monitor': 'gemma-large'} matches 0 cells; it must match exactly one |  |  |  |
| P5a size-diverse council vs its best member | action | skipped | Council 'size-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action'} matches 0 cells; it must match exactly one |  |  |  |
| P5a size-diverse council vs its best member | all | skipped | Council 'size-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all'} matches 0 cells; it must match exactly one |  |  |  |
| P5a size-diverse council vs its best member | cot | skipped | Council 'size-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot'} matches 0 cells; it must match exactly one |  |  |  |
| P5b family-diverse council vs its best member | action | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action'} matches 0 cells; it must match exactly one |  |  |  |
| P5b family-diverse council vs its best member | all | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all'} matches 0 cells; it must match exactly one |  |  |  |
| P5b family-diverse council vs its best member | cot | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot'} matches 0 cells; it must match exactly one |  |  |  |
| P5c family-diverse council vs same-model control | action | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'action'} matches 0 cells; it must match exactly one |  |  |  |
| P5c family-diverse council vs same-model control | all | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'all'} matches 0 cells; it must match exactly one |  |  |  |
| P5c family-diverse council vs same-model control | cot | skipped | Council 'family-diverse' with settings {'task_context': 'none', 'hierarchy': 'upstream-limits', 'partial_cot': 'off', 'reasoning': 'default', 'scope': 'cot'} matches 0 cells; it must match exactly one |  |  |  |

## Combined results: all Qwen3 and Gemma 4 monitors

Added 2026-11-24 from stored results only; no model was contacted. The `qwen3-32b` and `qwen3-14b` rows are the cells tabulated above. The other six monitors come from these files, scored on the same rollouts with 4 samples per pair and 2000 bootstrap replicates (seed 0): `runs/baseline/metrics.json`, `runs/parallel/gemma4-e2b/baseline/metrics.json`, `runs/parallel/gemma4-e4b/baseline/metrics.json`, `runs/parallel/gemma4-12b/baseline/metrics.json`, `runs/parallel/gemma4-31b/baseline/metrics.json`.

This section is assembled by hand, so re-running `scripts/make_report.py --out reports/baseline.md` overwrites it; the numbers stay reproducible from the files listed above.

### g-mean² (clean), both told objectives pooled

Primary metric, higher is better. Sorted by the `all` column.

| monitor | relation to the agent | action | cot | all |
| --- | --- | --- | --- | --- |
| gemma4-31b | different_family | 0.782 [0.695, 0.866] | 0.846 [0.780, 0.909] | 0.836 [0.757, 0.909] |
| gemma4-12b | different_family | 0.742 [0.673, 0.810] | 0.791 [0.707, 0.871] | 0.838 [0.765, 0.911] |
| qwen3-14b | same_model | 0.768 [0.692, 0.842] | 0.806 [0.739, 0.872] | 0.776 [0.716, 0.835] |
| gemma4-e4b | different_family | 0.712 [0.650, 0.770] | 0.666 [0.569, 0.762] | 0.774 [0.689, 0.856] |
| qwen3-4b | same_family_smaller | 0.739 [0.665, 0.814] | 0.721 [0.652, 0.789] | 0.765 [0.692, 0.834] |
| qwen3-32b | same_family_larger | 0.712 [0.636, 0.784] | 0.746 [0.678, 0.816] | 0.716 [0.641, 0.788] |
| gemma4-e2b | different_family | 0.616 [0.521, 0.706] | 0.859 [0.687, 1.000] | 0.692 [0.179, 0.946] |
| qwen3-1.7b | same_family_smaller | 0.343 [0.232, 0.466] | 0.262 [0.182, 0.352] | 0.259 [0.163, 0.360] |

### Full headline table, both told objectives pooled

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| gemma4-31b · action · context none | 0.988 [0.957, 1.000] | 0.792 [0.712, 0.869] | 0.782 [0.695, 0.866] | 1.000 [1.000, 1.000] |
| gemma4-31b · cot · context none | 0.976 [0.927, 1.000] | 0.867 [0.808, 0.924] | 0.846 [0.780, 0.909] | 1.000 [1.000, 1.000] |
| gemma4-31b · all · context none | 0.963 [0.907, 1.000] | 0.867 [0.804, 0.923] | 0.836 [0.757, 0.909] | 1.000 [1.000, 1.000] |
| gemma4-12b · action · context none | 0.994 [0.976, 1.000] | 0.746 [0.677, 0.814] | 0.742 [0.673, 0.810] | 0.998 [0.993, 1.000] |
| gemma4-12b · cot · context none | 0.967 [0.911, 1.000] | 0.818 [0.742, 0.894] | 0.791 [0.707, 0.871] | 0.953 [0.933, 0.972] |
| gemma4-12b · all · context none | 0.975 [0.925, 1.000] | 0.859 [0.785, 0.924] | 0.838 [0.765, 0.911] | 0.980 [0.965, 0.992] |
| qwen3-14b · action · context none | 0.970 [0.921, 1.000] | 0.792 [0.723, 0.859] | 0.768 [0.692, 0.842] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.963 [0.917, 1.000] | 0.837 [0.784, 0.890] | 0.806 [0.739, 0.872] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 0.976 [0.933, 1.000] | 0.795 [0.739, 0.854] | 0.776 [0.716, 0.835] | 1.000 [1.000, 1.000] |
| gemma4-e4b · action · context none | 0.994 [0.974, 1.000] | 0.716 [0.659, 0.772] | 0.712 [0.650, 0.770] | 1.000 [1.000, 1.000] |
| gemma4-e4b · cot · context none | 0.933 [0.864, 1.000] | 0.714 [0.622, 0.796] | 0.666 [0.569, 0.762] | 0.995 [0.987, 1.000] |
| gemma4-e4b · all · context none | 0.939 [0.871, 1.000] | 0.824 [0.763, 0.885] | 0.774 [0.689, 0.856] | 0.992 [0.980, 1.000] |
| qwen3-4b · action · context none | 0.976 [0.939, 1.000] | 0.758 [0.690, 0.825] | 0.739 [0.665, 0.814] | 1.000 [1.000, 1.000] |
| qwen3-4b · cot · context none | 0.933 [0.878, 0.981] | 0.773 [0.708, 0.837] | 0.721 [0.652, 0.789] | 1.000 [1.000, 1.000] |
| qwen3-4b · all · context none | 0.927 [0.867, 0.981] | 0.826 [0.770, 0.879] | 0.765 [0.692, 0.834] | 1.000 [1.000, 1.000] |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.712 [0.636, 0.784] | 0.712 [0.636, 0.784] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.951 [0.886, 1.000] | 0.784 [0.728, 0.843] | 0.746 [0.678, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.945 [0.881, 1.000] | 0.758 [0.697, 0.814] | 0.716 [0.641, 0.788] | 1.000 [1.000, 1.000] |
| gemma4-e2b · action · context none | 0.977 [0.931, 1.000] | 0.631 [0.537, 0.718] | 0.616 [0.521, 0.706] | 0.602 [0.545, 0.658] |
| gemma4-e2b · cot · context none | 0.960 [0.833, 1.000] | 0.895 [0.750, 1.000] | 0.859 [0.687, 1.000] | 0.127 [0.093, 0.162] |
| gemma4-e2b · all · context none | 0.833 [0.250, 1.000] | 0.831 [0.677, 0.952] | 0.692 [0.179, 0.946] | 0.147 [0.107, 0.185] |
| qwen3-1.7b · action · context none | 0.405 [0.278, 0.547] | 0.848 [0.780, 0.904] | 0.343 [0.232, 0.466] | 0.730 [0.680, 0.780] |
| qwen3-1.7b · cot · context none | 0.392 [0.276, 0.517] | 0.668 [0.591, 0.745] | 0.262 [0.182, 0.352] | 0.723 [0.677, 0.768] |
| qwen3-1.7b · all · context none | 0.436 [0.286, 0.577] | 0.594 [0.496, 0.689] | 0.259 [0.163, 0.360] | 0.530 [0.473, 0.585] |

### Full headline table, told the malicious objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| gemma4-31b · action · context none | 0.977 [0.924, 1.000] | 0.652 [0.529, 0.772] | 0.637 [0.516, 0.761] | 1.000 [1.000, 1.000] |
| gemma4-31b · cot · context none | 1.000 [1.000, 1.000] | 0.788 [0.684, 0.894] | 0.788 [0.684, 0.894] | 1.000 [1.000, 1.000] |
| gemma4-31b · all · context none | 0.977 [0.927, 1.000] | 0.795 [0.691, 0.887] | 0.777 [0.676, 0.872] | 1.000 [1.000, 1.000] |
| gemma4-12b · action · context none | 1.000 [1.000, 1.000] | 0.598 [0.493, 0.703] | 0.598 [0.493, 0.703] | 1.000 [1.000, 1.000] |
| gemma4-12b · cot · context none | 0.987 [0.950, 1.000] | 0.765 [0.662, 0.871] | 0.755 [0.652, 0.864] | 0.960 [0.927, 0.987] |
| gemma4-12b · all · context none | 1.000 [1.000, 1.000] | 0.779 [0.667, 0.886] | 0.779 [0.667, 0.886] | 0.973 [0.947, 0.993] |
| qwen3-14b · action · context none | 1.000 [1.000, 1.000] | 0.636 [0.516, 0.757] | 0.636 [0.516, 0.757] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.966 [0.896, 1.000] | 0.758 [0.654, 0.856] | 0.732 [0.635, 0.831] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 1.000 [1.000, 1.000] | 0.682 [0.576, 0.787] | 0.682 [0.576, 0.787] | 1.000 [1.000, 1.000] |
| gemma4-e4b · action · context none | 0.989 [0.955, 1.000] | 0.530 [0.445, 0.618] | 0.524 [0.439, 0.614] | 1.000 [1.000, 1.000] |
| gemma4-e4b · cot · context none | 0.955 [0.875, 1.000] | 0.554 [0.429, 0.675] | 0.529 [0.406, 0.654] | 0.993 [0.980, 1.000] |
| gemma4-e4b · all · context none | 0.955 [0.875, 1.000] | 0.692 [0.570, 0.805] | 0.661 [0.543, 0.785] | 0.990 [0.973, 1.000] |
| qwen3-4b · action · context none | 0.989 [0.955, 1.000] | 0.614 [0.500, 0.735] | 0.607 [0.493, 0.728] | 1.000 [1.000, 1.000] |
| qwen3-4b · cot · context none | 0.977 [0.920, 1.000] | 0.735 [0.637, 0.831] | 0.718 [0.617, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-4b · all · context none | 0.955 [0.880, 1.000] | 0.773 [0.684, 0.855] | 0.738 [0.642, 0.828] | 1.000 [1.000, 1.000] |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.530 [0.432, 0.636] | 0.530 [0.432, 0.636] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 1.000 [1.000, 1.000] | 0.636 [0.530, 0.750] | 0.636 [0.530, 0.750] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.989 [0.957, 1.000] | 0.606 [0.508, 0.699] | 0.599 [0.502, 0.695] | 1.000 [1.000, 1.000] |
| gemma4-e2b · action · context none | 0.980 [0.918, 1.000] | 0.442 [0.325, 0.556] | 0.433 [0.321, 0.543] | 0.640 [0.570, 0.713] |
| gemma4-e2b · cot · context none | 0.938 [0.739, 1.000] | 0.765 [0.455, 1.000] | 0.717 [0.410, 1.000] | 0.130 [0.083, 0.177] |
| gemma4-e2b · all · context none | 1.000 [1.000, 1.000] | 0.724 [0.467, 0.947] | 0.724 [0.452, 0.947] | 0.143 [0.093, 0.197] |
| qwen3-1.7b · action · context none | 0.571 [0.367, 0.778] | 0.752 [0.632, 0.853] | 0.430 [0.269, 0.606] | 0.677 [0.610, 0.740] |
| qwen3-1.7b · cot · context none | 0.524 [0.333, 0.742] | 0.667 [0.562, 0.768] | 0.349 [0.218, 0.504] | 0.727 [0.667, 0.783] |
| qwen3-1.7b · all · context none | 0.568 [0.300, 0.794] | 0.558 [0.437, 0.686] | 0.317 [0.163, 0.482] | 0.560 [0.487, 0.630] |

### Full headline table, told the benign objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| gemma4-31b · action · context none | 1.000 [1.000, 1.000] | 0.932 [0.844, 1.000] | 0.932 [0.844, 1.000] | 1.000 [1.000, 1.000] |
| gemma4-31b · cot · context none | 0.947 [0.850, 1.000] | 0.947 [0.871, 1.000] | 0.897 [0.783, 0.993] | 1.000 [1.000, 1.000] |
| gemma4-31b · all · context none | 0.947 [0.850, 1.000] | 0.939 [0.853, 1.000] | 0.890 [0.769, 0.985] | 1.000 [1.000, 1.000] |
| gemma4-12b · action · context none | 0.987 [0.950, 1.000] | 0.894 [0.801, 0.977] | 0.882 [0.786, 0.970] | 0.997 [0.987, 1.000] |
| gemma4-12b · cot · context none | 0.945 [0.842, 1.000] | 0.871 [0.766, 0.963] | 0.823 [0.691, 0.941] | 0.947 [0.920, 0.973] |
| gemma4-12b · all · context none | 0.947 [0.850, 1.000] | 0.939 [0.868, 0.992] | 0.890 [0.783, 0.978] | 0.987 [0.967, 1.000] |
| qwen3-14b · action · context none | 0.934 [0.841, 1.000] | 0.947 [0.875, 1.000] | 0.885 [0.778, 0.979] | 1.000 [1.000, 1.000] |
| qwen3-14b · cot · context none | 0.961 [0.893, 1.000] | 0.917 [0.846, 0.977] | 0.880 [0.794, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-14b · all · context none | 0.947 [0.861, 1.000] | 0.909 [0.839, 0.969] | 0.861 [0.764, 0.941] | 1.000 [1.000, 1.000] |
| gemma4-e4b · action · context none | 1.000 [1.000, 1.000] | 0.902 [0.815, 0.977] | 0.902 [0.815, 0.977] | 1.000 [1.000, 1.000] |
| gemma4-e4b · cot · context none | 0.908 [0.789, 1.000] | 0.871 [0.780, 0.955] | 0.791 [0.665, 0.916] | 0.997 [0.987, 1.000] |
| gemma4-e4b · all · context none | 0.920 [0.807, 1.000] | 0.955 [0.882, 1.000] | 0.878 [0.757, 0.985] | 0.993 [0.980, 1.000] |
| qwen3-4b · action · context none | 0.961 [0.893, 1.000] | 0.902 [0.818, 0.971] | 0.866 [0.770, 0.953] | 1.000 [1.000, 1.000] |
| qwen3-4b · cot · context none | 0.882 [0.779, 0.972] | 0.811 [0.720, 0.904] | 0.715 [0.600, 0.828] | 1.000 [1.000, 1.000] |
| qwen3-4b · all · context none | 0.895 [0.789, 0.986] | 0.879 [0.790, 0.953] | 0.786 [0.671, 0.896] | 1.000 [1.000, 1.000] |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.894 [0.809, 0.970] | 0.894 [0.809, 0.970] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.895 [0.773, 1.000] | 0.932 [0.858, 0.985] | 0.834 [0.703, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.895 [0.773, 1.000] | 0.909 [0.826, 0.978] | 0.813 [0.682, 0.941] | 1.000 [1.000, 1.000] |
| gemma4-e2b · action · context none | 0.973 [0.891, 1.000] | 0.859 [0.740, 0.958] | 0.836 [0.707, 0.944] | 0.563 [0.487, 0.633] |
| gemma4-e2b · cot · context none | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.123 [0.077, 0.173] |
| gemma4-e2b · all · context none | 0.750 [0.000, 1.000] | 0.933 [0.778, 1.000] | 0.700 [0.000, 1.000] | 0.150 [0.093, 0.200] |
| qwen3-1.7b · action · context none | 0.238 [0.085, 0.424] | 0.931 [0.866, 0.982] | 0.222 [0.077, 0.397] | 0.783 [0.720, 0.840] |
| qwen3-1.7b · cot · context none | 0.291 [0.156, 0.449] | 0.670 [0.549, 0.793] | 0.195 [0.101, 0.310] | 0.720 [0.660, 0.777] |
| qwen3-1.7b · all · context none | 0.317 [0.147, 0.486] | 0.635 [0.485, 0.781] | 0.201 [0.092, 0.334] | 0.500 [0.433, 0.567] |

### Settings

| monitor | relation to the agent | scope | context | hierarchy | units | complete |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3-32b | same_family_larger | action | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | cot | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | all | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | action | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | cot | none | upstream-limits | 600/600 | yes |
| qwen3-14b | same_model | all | none | upstream-limits | 600/600 | yes |
| qwen3-1.7b | same_family_smaller | action | none | upstream-limits | 600/600 | yes |
| qwen3-1.7b | same_family_smaller | cot | none | upstream-limits | 600/600 | yes |
| qwen3-1.7b | same_family_smaller | all | none | upstream-limits | 600/600 | yes |
| qwen3-4b | same_family_smaller | action | none | upstream-limits | 600/600 | yes |
| qwen3-4b | same_family_smaller | cot | none | upstream-limits | 600/600 | yes |
| qwen3-4b | same_family_smaller | all | none | upstream-limits | 600/600 | yes |
| gemma4-e2b | different_family | action | none | upstream-limits | 600/600 | yes |
| gemma4-e2b | different_family | cot | none | upstream-limits | 600/600 | yes |
| gemma4-e2b | different_family | all | none | upstream-limits | 600/600 | yes |
| gemma4-e4b | different_family | action | none | upstream-limits | 600/600 | yes |
| gemma4-e4b | different_family | cot | none | upstream-limits | 600/600 | yes |
| gemma4-e4b | different_family | all | none | upstream-limits | 600/600 | yes |
| gemma4-12b | different_family | action | none | upstream-limits | 600/600 | yes |
| gemma4-12b | different_family | cot | none | upstream-limits | 600/600 | yes |
| gemma4-12b | different_family | all | none | upstream-limits | 600/600 | yes |
| gemma4-31b | different_family | action | none | upstream-limits | 600/600 | yes |
| gemma4-31b | different_family | cot | none | upstream-limits | 600/600 | yes |
| gemma4-31b | different_family | all | none | upstream-limits | 600/600 | yes |

### Caveats specific to these rows

* `qwen3-1.7b` was served with `--enforce-eager`: the compiled/CUDA-graph path hit an intermittent illegal memory access (vLLM 0.11, mixed prefill+decode batches), so eager was used to finish the cell. Eager costs about 1.4x throughput and does not change the verdicts.
* `gemma4-e2b` `cot` and `all` are **not comparable** with the other rows: coverage is 0.127 and 0.147, so only a handful of positive pairs carry a valid verdict. That is a format-compliance failure, not weak detection; its `action` row (coverage 0.602) is the only usable one.
* `qwen3-1.7b` coverage is 0.730 / 0.723 / 0.530, so its rates describe only the units it could answer at all.
* `gemma4-12b` and `gemma4-31b` units live in `runs/parallel/<monitor>/baseline` (submitted with `--parallel`); they are the same 600 units per cell as every other row.
* The three tasks are held fixed in the bootstrap, as stated in the caveats above: intervals do not describe generalization to new tasks.

