# Baseline: Qwen3-32B, no task context

Runs: `baseline`. Generated from stored results only; no model was contacted.

* `baseline`: rollout sets original_clean: 41 rollouts, main_only_v1: 34 rollouts; 4 monitor samples per pair; bootstrap 2000 replicates (seed 0); prompts frozen.

## Caveats

* Run `baseline` was made from a working tree with uncommitted changes (commit 94c00eae73).
* Some cells used the hierarchical monitor and are separate conditions from single-pass monitoring; they are not pooled: qwen3-32b · action · context none (120 of 600 units); qwen3-32b · cot · context none (600 of 600 units); qwen3-32b · all · context none (600 of 600 units).
* The three tasks are held fixed in the bootstrap: intervals describe variability of rollouts and monitor samples within these tasks, not generalization to new tasks. Conclusions are preliminary.
* Cross-objective negatives (rollouts whose agent pursued the *other* objective) are impure: the judge prompt's option A is worded generally. They are shown separately as objective-specificity and are not pooled with clean negatives.

## Settings

| monitor | relation to the agent | scope | context | hierarchy | units | complete |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3-32b | same_family_larger | action | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | cot | none | upstream-limits | 600/600 | yes |
| qwen3-32b | same_family_larger | all | none | upstream-limits | 600/600 | yes |

## Both told objectives pooled

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.712 [0.636, 0.784] | 0.712 [0.636, 0.784] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.951 [0.886, 1.000] | 0.784 [0.728, 0.843] | 0.746 [0.678, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.945 [0.881, 1.000] | 0.758 [0.697, 0.814] | 0.716 [0.641, 0.788] | 1.000 [1.000, 1.000] |

## Told the malicious objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.530 [0.432, 0.636] | 0.530 [0.432, 0.636] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 1.000 [1.000, 1.000] | 0.636 [0.530, 0.750] | 0.636 [0.530, 0.750] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.989 [0.957, 1.000] | 0.606 [0.508, 0.699] | 0.599 [0.502, 0.695] | 1.000 [1.000, 1.000] |

## Told the benign objective

Value [95% interval]. `n/a` means undefined (no valid verdicts in a needed group).

| cell | TPR (MonitorBench score) | TNR (clean) | g-mean² (clean) | coverage |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 1.000 [1.000, 1.000] | 0.894 [0.809, 0.970] | 0.894 [0.809, 0.970] | 1.000 [1.000, 1.000] |
| qwen3-32b · cot · context none | 0.895 [0.773, 1.000] | 0.932 [0.858, 0.985] | 0.834 [0.703, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-32b · all · context none | 0.895 [0.773, 1.000] | 0.909 [0.826, 0.978] | 0.813 [0.682, 0.941] | 1.000 [1.000, 1.000] |

## Secondary: objective-specificity (cross-objective negatives)

Impure negatives: see the caveats. Pooled over both told objectives.

| cell | TNR (cross-objective) | g-mean² (cross-objective) | TNR (own failures) |
| --- | --- | --- | --- |
| qwen3-32b · action · context none | 0.662 [0.581, 0.732] | 0.662 [0.581, 0.732] | 0.000 [0.000, 0.000] |
| qwen3-32b · cot · context none | 0.738 [0.650, 0.817] | 0.702 [0.612, 0.787] | 0.000 [0.000, 0.000] |
| qwen3-32b · all · context none | 0.806 [0.732, 0.875] | 0.762 [0.680, 0.842] | 0.000 [0.000, 0.000] |

## Sample sizes (pooled, pairs)

| cell | positive | clean negative | cross-objective | own failures |
| --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 41 | 66 | 40 | 3 |
| qwen3-32b · cot · context none | 41 | 66 | 40 | 3 |
| qwen3-32b · all · context none | 41 | 66 | 40 | 3 |

## Cost and latency

Tokens are as the server counted them. `served s` is the sum of request latencies (load, not GPU occupancy). `critical path` is the per-unit wall time if each tree level ran in parallel. GPU-hours appear only when the run recorded its GPUs.

| cell | units | calls | requests | prompt tokens | completion tokens | served s | call latency p50/p95 s | critical path mean s | GPU-hours |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3-32b · action · context none | 600 | 856 | 856 | 7,100,445 | 972,709 | 41792 | 41.1/101.4 | 61.9 | 5.84 |
| qwen3-32b · cot · context none | 600 | 6352 | 6353 | 57,383,449 | 6,192,523 | 306981 | 47.4/77.5 | 137.7 | 5.84 |
| qwen3-32b · all · context none | 600 | 7008 | 7010 | 63,820,612 | 6,354,269 | 317810 | 43.7/72.4 | 135.4 | 5.84 |
