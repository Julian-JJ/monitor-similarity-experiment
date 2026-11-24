# Jev 1.14 — full context, sampled answers

Compare four sampled labels with the highest answer from the same Jev inference.

## How we ran it

Draw four labels locally from each saved vector using temperature 0.6, top-p 0.9 and seed 0. Pool the labels individually. No extra API requests and no sampling settings sent to Jev.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 76.2% | 100.0% | 38.6% | 0.614 | 41.9% |
| CoT | 150/150 | 87.4% | 96.3% | 18.2% | 0.788 | 72.5% |
| Combined | 150/150 | 88.1% | 93.3% | 15.2% | 0.792 | 63.1% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- All three input views were evaluated. These are four draws, not four independently generated analyses.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 77.1% | 100.0% | 37.5% | 0.625 | 41.9% |
| CoT | 135/135 | 86.8% | 95.9% | 18.7% | 0.781 | 75.8% |
| Combined | 137/137 | 88.1% | 92.8% | 14.8% | 0.790 | 64.9% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../jev/results-completed-34426786/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/jev-variants-20261123/full/`
