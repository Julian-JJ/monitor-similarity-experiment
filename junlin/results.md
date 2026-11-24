# Qwen and Gemma baseline results

**Status: reported results; raw cluster artifacts have not been verified locally.**

These tables preserve the combined report at `476f186`, `reports/baseline.md` (SHA-256 `c70f4dc819c1dc45d6ec5bc29338db14eb6ed01c325a19436dbeed7e89ed36b9`). Values and intervals were copied at the report's three-decimal precision. See [the validity review](review.md) before interpreting them.

## Experiment

Fixed actor: Qwen3-14B. Tasks: `bank_transfer_2`, `american_airlines_2`, and `spam_filter_update`. The reported dataset has 41 dual-objective and 34 main-task-only transcripts. Each monitor judges all 75 transcripts under both told objectives with four independent monitor samples: **600 units per scope, 1,800 per model, 14,400 across eight models**. These are monitor samples, not additional actor rollouts. Every cell was reported as 600/600 present; presence includes invalid verdicts.

The baseline uses no follow-up observations and no task plan; cached actor follow-ups are not used. Thinking is enabled. Nominal settings: temperature 0.6, top-p 0.9, context 32,768, output reserve 16,768, chunks 12,000 reference tokens, bins of six, margin 512, tool results truncated to 2,000 characters. Long traces use recursive aggregation. Serving versions, checkpoint pins and eager/kernel settings still need the cluster provenance audit.

`action` shows tool calls/results; `cot` shows reasoning and visible assistant text; `all` shows both. These repository scopes differ from pure CoT/Actions in Monitoring Monitorability. The A–D leaf prompt is vendored; the aggregation prompt and numerical limits are this repository's implementation of the [MonitorBench hierarchy](https://arxiv.org/html/2603.28590v1#A2.SS1).

## Pooled comparison

Score = TPR × clean-control TNR (`gmean2_clean`). Invalid verdicts are excluded from both rates; coverage is the fraction yielding valid verdicts, over all pair types. Compare score and coverage together. This follows the repository's existing scoring policy, which has not been changed.

| Monitor | Actions score / coverage | CoT score / coverage | All score / coverage |
| --- | --- | --- | --- |
| qwen3-1.7b | 0.343 / 0.730 | 0.262 / 0.723 | 0.259 / 0.530 |
| qwen3-4b | 0.739 / 1.000 | 0.721 / 1.000 | 0.765 / 1.000 |
| qwen3-14b | 0.768 / 1.000 | 0.806 / 1.000 | 0.776 / 1.000 |
| qwen3-32b | 0.712 / 1.000 | 0.746 / 1.000 | 0.716 / 1.000 |
| gemma4-e2b | 0.616 / 0.602 | 0.859 / 0.127 | 0.692 / 0.147 |
| gemma4-e4b | 0.712 / 1.000 | 0.666 / 0.995 | 0.774 / 0.992 |
| gemma4-12b | 0.742 / 0.998 | 0.791 / 0.953 | 0.838 / 0.980 |
| gemma4-31b | 0.782 / 1.000 | 0.846 / 1.000 | 0.836 / 1.000 |

Gemma E2B's CoT score (0.859) is conditional on only 12.7% coverage; it does not establish superior performance on the full set. Qwen3-1.7B also has substantial invalid rates. Gemma 12B and 31B have similar reported all-message point estimates; these tables alone do not establish a significant difference. Gemma E2B/E4B names refer to effective sizes; the registry lists 5.1B/8.0B total parameters.

## Full reported estimates

Entries are estimate [95% interval]. The recorded method is 2,000 bootstrap replicates, seed 0, resampling rollouts within task/variant strata and monitor samples within pairs. The three tasks are held fixed; intervals do not measure generalization to unseen tasks. Exact values and denominators require the raw audit.

### Pooled told objectives

| Monitor | Scope | TPR | Clean TNR | Score | Coverage |
| --- | --- | --- | --- | --- | --- |
| qwen3-1.7b | action | 0.405 [0.278, 0.547] | 0.848 [0.780, 0.904] | 0.343 [0.232, 0.466] | 0.730 [0.680, 0.780] |
| qwen3-1.7b | cot | 0.392 [0.276, 0.517] | 0.668 [0.591, 0.745] | 0.262 [0.182, 0.352] | 0.723 [0.677, 0.768] |
| qwen3-1.7b | all | 0.436 [0.286, 0.577] | 0.594 [0.496, 0.689] | 0.259 [0.163, 0.360] | 0.530 [0.473, 0.585] |
| qwen3-4b | action | 0.976 [0.939, 1.000] | 0.758 [0.690, 0.825] | 0.739 [0.665, 0.814] | 1.000 [1.000, 1.000] |
| qwen3-4b | cot | 0.933 [0.878, 0.981] | 0.773 [0.708, 0.837] | 0.721 [0.652, 0.789] | 1.000 [1.000, 1.000] |
| qwen3-4b | all | 0.927 [0.867, 0.981] | 0.826 [0.770, 0.879] | 0.765 [0.692, 0.834] | 1.000 [1.000, 1.000] |
| qwen3-14b | action | 0.970 [0.921, 1.000] | 0.792 [0.723, 0.859] | 0.768 [0.692, 0.842] | 1.000 [1.000, 1.000] |
| qwen3-14b | cot | 0.963 [0.917, 1.000] | 0.837 [0.784, 0.890] | 0.806 [0.739, 0.872] | 1.000 [1.000, 1.000] |
| qwen3-14b | all | 0.976 [0.933, 1.000] | 0.795 [0.739, 0.854] | 0.776 [0.716, 0.835] | 1.000 [1.000, 1.000] |
| qwen3-32b | action | 1.000 [1.000, 1.000] | 0.712 [0.636, 0.784] | 0.712 [0.636, 0.784] | 1.000 [1.000, 1.000] |
| qwen3-32b | cot | 0.951 [0.886, 1.000] | 0.784 [0.728, 0.843] | 0.746 [0.678, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-32b | all | 0.945 [0.881, 1.000] | 0.758 [0.697, 0.814] | 0.716 [0.641, 0.788] | 1.000 [1.000, 1.000] |
| gemma4-e2b | action | 0.977 [0.931, 1.000] | 0.631 [0.537, 0.718] | 0.616 [0.521, 0.706] | 0.602 [0.545, 0.658] |
| gemma4-e2b | cot | 0.960 [0.833, 1.000] | 0.895 [0.750, 1.000] | 0.859 [0.687, 1.000] | 0.127 [0.093, 0.162] |
| gemma4-e2b | all | 0.833 [0.250, 1.000] | 0.831 [0.677, 0.952] | 0.692 [0.179, 0.946] | 0.147 [0.107, 0.185] |
| gemma4-e4b | action | 0.994 [0.974, 1.000] | 0.716 [0.659, 0.772] | 0.712 [0.650, 0.770] | 1.000 [1.000, 1.000] |
| gemma4-e4b | cot | 0.933 [0.864, 1.000] | 0.714 [0.622, 0.796] | 0.666 [0.569, 0.762] | 0.995 [0.987, 1.000] |
| gemma4-e4b | all | 0.939 [0.871, 1.000] | 0.824 [0.763, 0.885] | 0.774 [0.689, 0.856] | 0.992 [0.980, 1.000] |
| gemma4-12b | action | 0.994 [0.976, 1.000] | 0.746 [0.677, 0.814] | 0.742 [0.673, 0.810] | 0.998 [0.993, 1.000] |
| gemma4-12b | cot | 0.967 [0.911, 1.000] | 0.818 [0.742, 0.894] | 0.791 [0.707, 0.871] | 0.953 [0.933, 0.972] |
| gemma4-12b | all | 0.975 [0.925, 1.000] | 0.859 [0.785, 0.924] | 0.838 [0.765, 0.911] | 0.980 [0.965, 0.992] |
| gemma4-31b | action | 0.988 [0.957, 1.000] | 0.792 [0.712, 0.869] | 0.782 [0.695, 0.866] | 1.000 [1.000, 1.000] |
| gemma4-31b | cot | 0.976 [0.927, 1.000] | 0.867 [0.808, 0.924] | 0.846 [0.780, 0.909] | 1.000 [1.000, 1.000] |
| gemma4-31b | all | 0.963 [0.907, 1.000] | 0.867 [0.804, 0.923] | 0.836 [0.757, 0.909] | 1.000 [1.000, 1.000] |

### Malicious told objectives

| Monitor | Scope | TPR | Clean TNR | Score | Coverage |
| --- | --- | --- | --- | --- | --- |
| qwen3-1.7b | action | 0.571 [0.367, 0.778] | 0.752 [0.632, 0.853] | 0.430 [0.269, 0.606] | 0.677 [0.610, 0.740] |
| qwen3-1.7b | cot | 0.524 [0.333, 0.742] | 0.667 [0.562, 0.768] | 0.349 [0.218, 0.504] | 0.727 [0.667, 0.783] |
| qwen3-1.7b | all | 0.568 [0.300, 0.794] | 0.558 [0.437, 0.686] | 0.317 [0.163, 0.482] | 0.560 [0.487, 0.630] |
| qwen3-4b | action | 0.989 [0.955, 1.000] | 0.614 [0.500, 0.735] | 0.607 [0.493, 0.728] | 1.000 [1.000, 1.000] |
| qwen3-4b | cot | 0.977 [0.920, 1.000] | 0.735 [0.637, 0.831] | 0.718 [0.617, 0.816] | 1.000 [1.000, 1.000] |
| qwen3-4b | all | 0.955 [0.880, 1.000] | 0.773 [0.684, 0.855] | 0.738 [0.642, 0.828] | 1.000 [1.000, 1.000] |
| qwen3-14b | action | 1.000 [1.000, 1.000] | 0.636 [0.516, 0.757] | 0.636 [0.516, 0.757] | 1.000 [1.000, 1.000] |
| qwen3-14b | cot | 0.966 [0.896, 1.000] | 0.758 [0.654, 0.856] | 0.732 [0.635, 0.831] | 1.000 [1.000, 1.000] |
| qwen3-14b | all | 1.000 [1.000, 1.000] | 0.682 [0.576, 0.787] | 0.682 [0.576, 0.787] | 1.000 [1.000, 1.000] |
| qwen3-32b | action | 1.000 [1.000, 1.000] | 0.530 [0.432, 0.636] | 0.530 [0.432, 0.636] | 1.000 [1.000, 1.000] |
| qwen3-32b | cot | 1.000 [1.000, 1.000] | 0.636 [0.530, 0.750] | 0.636 [0.530, 0.750] | 1.000 [1.000, 1.000] |
| qwen3-32b | all | 0.989 [0.957, 1.000] | 0.606 [0.508, 0.699] | 0.599 [0.502, 0.695] | 1.000 [1.000, 1.000] |
| gemma4-e2b | action | 0.980 [0.918, 1.000] | 0.442 [0.325, 0.556] | 0.433 [0.321, 0.543] | 0.640 [0.570, 0.713] |
| gemma4-e2b | cot | 0.938 [0.739, 1.000] | 0.765 [0.455, 1.000] | 0.717 [0.410, 1.000] | 0.130 [0.083, 0.177] |
| gemma4-e2b | all | 1.000 [1.000, 1.000] | 0.724 [0.467, 0.947] | 0.724 [0.452, 0.947] | 0.143 [0.093, 0.197] |
| gemma4-e4b | action | 0.989 [0.955, 1.000] | 0.530 [0.445, 0.618] | 0.524 [0.439, 0.614] | 1.000 [1.000, 1.000] |
| gemma4-e4b | cot | 0.955 [0.875, 1.000] | 0.554 [0.429, 0.675] | 0.529 [0.406, 0.654] | 0.993 [0.980, 1.000] |
| gemma4-e4b | all | 0.955 [0.875, 1.000] | 0.692 [0.570, 0.805] | 0.661 [0.543, 0.785] | 0.990 [0.973, 1.000] |
| gemma4-12b | action | 1.000 [1.000, 1.000] | 0.598 [0.493, 0.703] | 0.598 [0.493, 0.703] | 1.000 [1.000, 1.000] |
| gemma4-12b | cot | 0.987 [0.950, 1.000] | 0.765 [0.662, 0.871] | 0.755 [0.652, 0.864] | 0.960 [0.927, 0.987] |
| gemma4-12b | all | 1.000 [1.000, 1.000] | 0.779 [0.667, 0.886] | 0.779 [0.667, 0.886] | 0.973 [0.947, 0.993] |
| gemma4-31b | action | 0.977 [0.924, 1.000] | 0.652 [0.529, 0.772] | 0.637 [0.516, 0.761] | 1.000 [1.000, 1.000] |
| gemma4-31b | cot | 1.000 [1.000, 1.000] | 0.788 [0.684, 0.894] | 0.788 [0.684, 0.894] | 1.000 [1.000, 1.000] |
| gemma4-31b | all | 0.977 [0.927, 1.000] | 0.795 [0.691, 0.887] | 0.777 [0.676, 0.872] | 1.000 [1.000, 1.000] |

### Benign told objectives

| Monitor | Scope | TPR | Clean TNR | Score | Coverage |
| --- | --- | --- | --- | --- | --- |
| qwen3-1.7b | action | 0.238 [0.085, 0.424] | 0.931 [0.866, 0.982] | 0.222 [0.077, 0.397] | 0.783 [0.720, 0.840] |
| qwen3-1.7b | cot | 0.291 [0.156, 0.449] | 0.670 [0.549, 0.793] | 0.195 [0.101, 0.310] | 0.720 [0.660, 0.777] |
| qwen3-1.7b | all | 0.317 [0.147, 0.486] | 0.635 [0.485, 0.781] | 0.201 [0.092, 0.334] | 0.500 [0.433, 0.567] |
| qwen3-4b | action | 0.961 [0.893, 1.000] | 0.902 [0.818, 0.971] | 0.866 [0.770, 0.953] | 1.000 [1.000, 1.000] |
| qwen3-4b | cot | 0.882 [0.779, 0.972] | 0.811 [0.720, 0.904] | 0.715 [0.600, 0.828] | 1.000 [1.000, 1.000] |
| qwen3-4b | all | 0.895 [0.789, 0.986] | 0.879 [0.790, 0.953] | 0.786 [0.671, 0.896] | 1.000 [1.000, 1.000] |
| qwen3-14b | action | 0.934 [0.841, 1.000] | 0.947 [0.875, 1.000] | 0.885 [0.778, 0.979] | 1.000 [1.000, 1.000] |
| qwen3-14b | cot | 0.961 [0.893, 1.000] | 0.917 [0.846, 0.977] | 0.880 [0.794, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-14b | all | 0.947 [0.861, 1.000] | 0.909 [0.839, 0.969] | 0.861 [0.764, 0.941] | 1.000 [1.000, 1.000] |
| qwen3-32b | action | 1.000 [1.000, 1.000] | 0.894 [0.809, 0.970] | 0.894 [0.809, 0.970] | 1.000 [1.000, 1.000] |
| qwen3-32b | cot | 0.895 [0.773, 1.000] | 0.932 [0.858, 0.985] | 0.834 [0.703, 0.956] | 1.000 [1.000, 1.000] |
| qwen3-32b | all | 0.895 [0.773, 1.000] | 0.909 [0.826, 0.978] | 0.813 [0.682, 0.941] | 1.000 [1.000, 1.000] |
| gemma4-e2b | action | 0.973 [0.891, 1.000] | 0.859 [0.740, 0.958] | 0.836 [0.707, 0.944] | 0.563 [0.487, 0.633] |
| gemma4-e2b | cot | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.123 [0.077, 0.173] |
| gemma4-e2b | all | 0.750 [0.000, 1.000] | 0.933 [0.778, 1.000] | 0.700 [0.000, 1.000] | 0.150 [0.093, 0.200] |
| gemma4-e4b | action | 1.000 [1.000, 1.000] | 0.902 [0.815, 0.977] | 0.902 [0.815, 0.977] | 1.000 [1.000, 1.000] |
| gemma4-e4b | cot | 0.908 [0.789, 1.000] | 0.871 [0.780, 0.955] | 0.791 [0.665, 0.916] | 0.997 [0.987, 1.000] |
| gemma4-e4b | all | 0.920 [0.807, 1.000] | 0.955 [0.882, 1.000] | 0.878 [0.757, 0.985] | 0.993 [0.980, 1.000] |
| gemma4-12b | action | 0.987 [0.950, 1.000] | 0.894 [0.801, 0.977] | 0.882 [0.786, 0.970] | 0.997 [0.987, 1.000] |
| gemma4-12b | cot | 0.945 [0.842, 1.000] | 0.871 [0.766, 0.963] | 0.823 [0.691, 0.941] | 0.947 [0.920, 0.973] |
| gemma4-12b | all | 0.947 [0.850, 1.000] | 0.939 [0.868, 0.992] | 0.890 [0.783, 0.978] | 0.987 [0.967, 1.000] |
| gemma4-31b | action | 1.000 [1.000, 1.000] | 0.932 [0.844, 1.000] | 0.932 [0.844, 1.000] | 1.000 [1.000, 1.000] |
| gemma4-31b | cot | 0.947 [0.850, 1.000] | 0.947 [0.871, 1.000] | 0.897 [0.783, 0.993] | 1.000 [1.000, 1.000] |
| gemma4-31b | all | 0.947 [0.850, 1.000] | 0.939 [0.853, 1.000] | 0.890 [0.769, 0.985] | 1.000 [1.000, 1.000] |

## Sources and reproduction

Qwen cells were reported from `$ME/runs/baseline/metrics.json`. Each Gemma was reported from `$ME/runs/parallel/<model>/baseline/metrics.json`. The later Qwen1.7B parallel run, if present, must be compared separately rather than silently substituted. The raw files are currently only on the cluster.

Regenerate these tables with `python3 junlin/compile_results.py`. On the cluster, run `bash junlin/export_results.sh` to collect a small audit bundle at `junlin/results/cluster-audit.json`. It reads existing artifacts, checks coverage/identities/collection hashes and recomputes point estimates with unchanged scoring. It does not call models or rewrite the runs. Intervals are exported as recorded, not recalculated. Any findings require review; the exporter cannot prove provenance that was never recorded.

The machine-readable reported data are in [`results/reported-baseline.json`](results/reported-baseline.json). Timing values from the earlier report are omitted: runner session wall time measures the monitoring loop, not full GPU allocation/startup. Use Slurm accounting for total compute cost.
