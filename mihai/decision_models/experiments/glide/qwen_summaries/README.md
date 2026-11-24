# Qwen3-32B summaries → GLiDE-9B

Test whether a decision model benefits from reading compact evidence summaries instead of the raw transcript.

## How we ran it

Qwen greedily summarizes each shared chunk without an A–D verdict, targeting at most 350 words. Concatenate every summary in order and ask GLiDE-9B for one highest-probability A–D answer.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 89.7% | 90.2% | 10.6% | 0.807 | 12.5% |
| CoT | 141/150 | 86.3% | 94.7% | 18.8% | 0.770 | 5.6% |
| Combined | 138/150 | 92.9% | 97.4% | 10.2% | 0.875 | 10.8% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- 429/450 final cases completed: 150 Actions, 141 CoT and 138 Combined. The other 21 were blocked by missing valid Qwen summaries.
- There were no downstream decision-model inference failures. Missing summaries are never silently dropped.
- This is a two-model system; its cost includes Qwen summary generation.
- Downstream job duration: 5:17 for GLiDE. Qwen took 6:46:08 for greedy monitoring plus summary generation together.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 89.5% | 90.2% | 10.9% | 0.804 | 12.5% |
| CoT | 135/135 | 86.0% | 94.6% | 19.0% | 0.766 | 3.1% |
| Combined | 137/137 | 92.8% | 97.4% | 10.2% | 0.875 | 10.8% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../summary-results-20261124/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/glide-summaries/`
