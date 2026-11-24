# Qwen3-32B — sampled baseline

Provide the original same-family generative-monitor reference for the decision-model experiments.

## How we ran it

Original MonitorBench prompt; thinking enabled; temperature 0.6, top-p 0.9. Four independently generated analyses and A–D answers per case, pooled individually. The baseline hierarchy combines chunk analyses when the rendered input does not fit.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 82.2% | 100.0% | 28.8% | 0.712 | 33.8% |
| CoT | 150/150 | 84.8% | 95.1% | 21.6% | 0.746 | 26.3% |
| Combined | 150/150 | 82.9% | 94.5% | 24.2% | 0.716 | 19.4% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- These are the original team baseline results, reused as reference conditions here.
- Four Qwen analyses are different from drawing four labels from one decision-model probability vector.
- Observed evaluation-session time on one H200: 5:50:32 across two sessions.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 82.9% | 100.0% | 28.1% | 0.719 | 33.8% |
| CoT | 135/135 | 86.0% | 97.3% | 20.6% | 0.772 | 22.7% |
| Combined | 137/137 | 83.5% | 94.1% | 23.3% | 0.722 | 18.9% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../comparisons/baseline-20261123/audit.json)

Raw cluster locations:

- `$BASELINE_RUN (exact provenance in comparisons/baseline-20261123/manifest.json)`
