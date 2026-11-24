# GLiDE-9B — chunks, maximum P(A)

Test whether judging smaller pieces helps detection, using the strongest local signal.

## How we ran it

Use the baseline chunk planner (12,000-token budget, single-pass-if-fits shortcut). Classify each chunk with A–D options and a partial-transcript notice. Take the maximum raw P(A) and flag at ≥ 0.5.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 89.7% | 92.7% | 12.1% | 0.814 | 12.5% |
| CoT | 150/150 | 97.2% | 92.7% | 0.0% | 0.927 | 17.5% |
| Combined | 150/150 | 96.3% | 92.7% | 1.5% | 0.913 | 22.5% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- All 2,834 chunk calls completed: 184 Actions, 1,256 CoT and 1,394 Combined.
- Maximum and average reuse the same calls; averaging is not weighted by chunk length.
- This is a binary threshold rule, not choosing the largest of A, B, C and D. Any missing chunk invalidates the case.
- Chunking and the final decision rule both differ from full-input highest-answer inference.
- Shared chunk job duration: 2:02:25, also including the new full Combined evaluation.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 90.5% | 92.7% | 10.9% | 0.825 | 12.5% |
| CoT | 135/135 | 98.0% | 94.6% | 0.0% | 0.946 | 18.8% |
| Combined | 137/137 | 95.9% | 92.1% | 1.7% | 0.905 | 24.3% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../variants/results-completed-34428767/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/glide-chunks/`
