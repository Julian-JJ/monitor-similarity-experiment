# Jev 1.14 — full context, highest answer

Measure whether Jev can detect the objective from the entire rendered transcript in one request.

## How we ran it

Send the same adapted state, instructions and A–D choices used for GLiDE to jev-1.14.0. Take the highest-probability option; A is detection. Enable long-context mode for CoT and Combined.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 73.8% | 100.0% | 42.4% | 0.576 | 45.0% |
| CoT | 150/150 | 89.7% | 95.1% | 13.6% | 0.822 | 80.0% |
| Combined | 150/150 | 93.5% | 95.1% | 7.6% | 0.879 | 67.5% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- All 450 requests completed. Hosted TypeSafe API; server hardware and memory are not exposed.
- Largest accepted pilot inputs: 26,884 Actions, 216,646 CoT and 229,506 Combined Jev tokens.
- Full-input production took 13:13. Mean recorded API latency: 0.19 s Actions, 0.96 s CoT, 1.08 s Combined.
- API latency includes network effects and is not a controlled hardware speed comparison.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 75.2% | 100.0% | 40.6% | 0.594 | 45.0% |
| CoT | 135/135 | 89.0% | 94.6% | 14.3% | 0.811 | 84.4% |
| Combined | 137/137 | 93.8% | 94.7% | 6.8% | 0.883 | 67.6% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../jev/results-completed-34426786/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/jev-variants-20261123/full/`
