# Qwen3-32B summaries → Jev 1.14

Test whether a decision model benefits from reading compact evidence summaries instead of the raw transcript.

## How we ran it

Qwen greedily summarizes each shared chunk without an A–D verdict, targeting at most 350 words. Concatenate every summary in order and ask Jev 1.14 for one highest-probability A–D answer.

## Results on all valid cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 150/150 | 84.1% | 95.1% | 22.7% | 0.735 | 22.5% |
| CoT | 141/150 | 72.5% | 100.0% | 43.8% | 0.563 | 44.4% |
| Combined | 138/150 | 78.6% | 100.0% | 35.6% | 0.644 | 32.4% |

Accuracy and G-mean² use positives and clean controls; cross-objective false alarms are separate. The view folders contain the saved decisions, labels used only for scoring, and exact counts.

## Notes

- 429/450 final cases completed: 150 Actions, 141 CoT and 138 Combined. The other 21 were blocked by missing valid Qwen summaries.
- There were no downstream decision-model inference failures. Missing summaries are never silently dropped.
- This is a two-model system; its cost includes Qwen summary generation.
- Downstream job duration: 8:59 for Jev. Qwen took 6:46:08 for greedy monitoring plus summary generation together.

## Results on the common comparison cases

| Input | Valid cases | Accuracy ↑ | TPR ↑ | Clean FPR ↓ | G-mean² ↑ | Cross FPR ↓ |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/148 | 84.8% | 95.1% | 21.9% | 0.743 | 22.5% |
| CoT | 135/135 | 72.0% | 100.0% | 44.4% | 0.556 | 43.8% |
| Combined | 137/137 | 78.4% | 100.0% | 35.6% | 0.644 | 32.4% |

These use the intersection of valid cases across every compared method in each input view. See [the complete comparison and caveats](../../../README.md).

## Files and provenance

[Exact results](results.json) · [Source hashes and settings](provenance.json) · [Audit 1](../../../summary-results-20261124/audit.json)

Raw cluster locations:

- `$PROJECT/mihai/decision_models/runs/jev-variants-20261123/summaries/`
