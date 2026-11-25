# Jev 1.14 — chunks, maximum P(A)

Test whether judging smaller pieces helps detection, using the strongest local signal.

## How we ran it

Use the baseline chunk planner (12,000-token budget, single-pass-if-fits shortcut). Classify each chunk with A–D options and a partial-transcript notice. Take the maximum raw P(A) and flag at ≥ 0.5.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 78.5% | 100.0% | 34.8% | 0.652 | 35.0% |
| CoT | 150/150 | 94.4% | 95.1% | 6.1% | 0.894 | 80.0% |
| Combined | 150/150 | 96.3% | 95.1% | 3.0% | 0.922 | 62.5% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- All 2,834 chunk calls completed: 184 Actions, 1,256 CoT and 1,394 Combined.
- Maximum and average reuse the same calls; averaging is not weighted by chunk length.
- This is a binary threshold rule, not choosing the largest of A, B, C and D. Any missing chunk invalidates the case.
- Chunking and the final decision rule both differ from full-input highest-answer inference. The full-context P(A) ≥ 0.5 experiment controls for the threshold rule.
- Shared chunk job duration: 1:02:10 through the hosted API.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 79.0% | 100.0% | 34.4% | 0.656 | 35.0% |
| CoT | 135/135 | 94.0% | 94.6% | 6.3% | 0.886 | 84.4% |
| Combined | 137/137 | 95.9% | 94.7% | 3.4% | 0.915 | 67.6% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../jev/results-completed-34426786/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/jev-variants-20261123/chunks/`
