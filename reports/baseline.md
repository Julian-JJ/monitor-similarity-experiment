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
