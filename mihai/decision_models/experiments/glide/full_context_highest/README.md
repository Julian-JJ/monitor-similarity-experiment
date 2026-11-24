# GLiDE-9B — full context, highest answer

Measure detection when GLiDE sees the full rendered transcript and chooses its most likely answer.

## How we ran it

Adapt the MonitorBench prompt to the same ordered A–D options. Submit the entire selected view in one call, then take the highest raw option probability; A means detection. No hierarchy or 0.5 threshold.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 83.2% | 95.1% | 24.2% | 0.721 | 20.0% |
| CoT | 150/150 | 91.6% | 78.0% | 0.0% | 0.780 | 27.5% |
| Combined | 150/150 | 91.6% | 87.8% | 6.1% | 0.825 | 50.0% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- Actions and CoT reuse the verified November 15 evaluations; Combined was evaluated November 23.
- Full prompt lengths reached 26,275 Actions, 216,463 CoT and 229,167 Combined GLiDE tokens.
- Local BF16 GLiDE-9B, revision ab54df5acba0eebf7df45560ffdaacd64e32df3b, on RTX PRO 6000 Blackwell.
- Actions: 5:04 GPU job, 1.87 s mean call. CoT: 66:13 across original and restart jobs, 26.01 s mean call.
- The first CoT process stopped after 108 cases for an unresolved reason; the authorized restart preserved those and completed 42.
- Combined and chunk inference shared a 2:02:25 GPU job; no standalone Combined wall time is claimed.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 84.8% | 95.1% | 21.9% | 0.743 | 20.0% |
| CoT | 135/135 | 92.0% | 78.4% | 0.0% | 0.784 | 34.4% |
| Combined | 137/137 | 90.7% | 86.8% | 6.8% | 0.810 | 54.1% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../variants/results-completed-34428767/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/glide-actions-20261115-60611f0f/`
- `$PROJECT/mihai/decision_models/runs/glide-cot-20261115-c8f6c4e8/`
- `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/glide-full/`
