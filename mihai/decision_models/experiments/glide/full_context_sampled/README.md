# GLiDE-9B — full context, sampled answers

Explore how sampling labels changes the same full-input classifier, alongside the sampled Qwen baseline.

## How we ran it

Reuse each full-input probability vector; apply temperature 0.6 and top-p 0.9, then draw four labels with seed 0. Count each draw separately; do not majority-vote. There are no additional model calls.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 83.4% | 94.5% | 23.5% | 0.723 | 23.1% |
| CoT | 150/150 | 84.6% | 62.8% | 1.9% | 0.616 | 19.4% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- Actions and CoT were evaluated. Sampled full Combined was not run.
- The four labels share one inference result; they are not four independent analyses.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 84.8% | 94.5% | 21.5% | 0.742 | 23.1% |
| CoT | 135/135 | 85.5% | 64.2% | 2.0% | 0.629 | 21.9% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../evaluations/glide-actions-20261115-60611f0f/final-audit.json) · [Audit 2](../../../evaluations/glide-cot-20261115-c8f6c4e8/final-audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/glide-actions-20261115-60611f0f/`
- `$PROJECT/mihai/decision_models/runs/glide-cot-20261115-c8f6c4e8/`
