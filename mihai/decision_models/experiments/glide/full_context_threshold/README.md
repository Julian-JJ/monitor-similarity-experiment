# GLiDE-9B — full context, P(A) ≥ 0.5

Compare full-input detection with chunk aggregation using the same binary probability threshold.

## How we ran it

Reuse the exact full-context responses from the highest-answer experiment. Flag only when the original raw P(A) is at least 0.5, including equality. Apply no sampling, temperature rescaling or top-p filtering. This compares A with the combined probability of B, C and D.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 90.7% | 92.7% | 10.6% | 0.829 | 12.5% |
| CoT | 150/150 | 82.2% | 53.7% | 0.0% | 0.537 | 2.5% |
| Combined | 150/150 | 89.7% | 73.2% | 0.0% | 0.732 | 20.0% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- All 450 full-context responses were verified against their saved requests and original argmax records. No new model or API calls.
- Prompts, input rendering, model versions and labels are identical to the full-context highest-answer experiment.
- Changed A alarms to negative decisions: 13 Actions, 21 CoT and 22 Combined, across all 150 cases per view.
- The original argmax results remain a separate experiment. Threshold results are point estimates; no new confidence intervals were computed.
- Full-context and chunk methods now share the 0.5 decision threshold; chunking still changes the input and includes a partial-transcript notice.
- This is offline rescoring, so original inference runtime is unchanged.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 90.5% | 92.7% | 10.9% | 0.825 | 12.5% |
| CoT | 135/135 | 84.0% | 56.8% | 0.0% | 0.568 | 3.1% |
| Combined | 137/137 | 88.7% | 71.1% | 0.0% | 0.711 | 21.6% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../full_context_threshold/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/glide-actions-20261115-60611f0f/`
- `$PROJECT/mihai/decision_models/runs/glide-cot-20261115-c8f6c4e8/`
- `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/glide-full/`
