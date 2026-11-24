# Qwen3-14B — sampled baseline

Provide the original same-family generative-monitor reference for the decision-model experiments.

## How we ran it

Original MonitorBench prompt; thinking enabled; temperature 0.6, top-p 0.9. Four independently generated analyses and A–D answers per case, pooled individually. The baseline hierarchy combines chunk analyses when the rendered input does not fit.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 86.0% | 97.0% | 20.8% | 0.768 | 29.4% |
| CoT | 150/150 | 88.6% | 96.3% | 16.3% | 0.806 | 25.0% |
| Combined | 150/150 | 86.4% | 97.6% | 20.5% | 0.776 | 32.5% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- These are the original team baseline results, reused as reference conditions here.
- Four Qwen analyses are different from drawing four labels from one decision-model probability vector.
- Observed evaluation-session time on one H200: 3:00:50.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 86.7% | 97.0% | 19.9% | 0.776 | 29.4% |
| CoT | 135/135 | 88.5% | 96.6% | 16.3% | 0.809 | 19.5% |
| Combined | 137/137 | 86.9% | 97.4% | 19.9% | 0.780 | 31.1% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../comparisons/baseline-20261123/audit.json)

Raw cluster locations:

- `$BASELINE_RUN (exact provenance in comparisons/baseline-20261123/manifest.json)`
