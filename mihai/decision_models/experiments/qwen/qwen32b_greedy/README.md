# Qwen3-32B — greedy baseline

Compare the decision models against a Qwen monitor that does not sample its generated tokens.

## How we ran it

Original prompt and baseline hierarchy; thinking enabled; temperature 0, top-p 1, one judgment per case. A is detection. Each hierarchy node has one attempt and a 16,768-token output cap.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/150 | 83.8% | 97.6% | 25.0% | 0.732 | 32.5% |
| CoT | 143/150 | 87.6% | 97.5% | 18.5% | 0.795 | 22.9% |
| Combined | 149/150 | 84.9% | 95.0% | 21.2% | 0.748 | 15.0% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- 440/450 valid judgments; all ten invalid judgments contain a node truncated at 16,768 output tokens.
- The initial launch failed before inference because the client environment lacked tokenizers; the corrected run is job 34371577.
- That job took 6:46:08 and also generated evidence summaries. This duration is not greedy-monitor-only runtime.
- The sampled baseline allowed two node attempts; this run allowed one. Decoder choice is not the only operational difference.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 83.8% | 97.6% | 25.0% | 0.732 | 32.5% |
| CoT | 135/135 | 88.0% | 97.3% | 17.5% | 0.803 | 21.9% |
| Combined | 137/137 | 85.6% | 94.7% | 20.3% | 0.755 | 13.5% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../variants/results-qwen-greedy-34584150/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/qwen/`
