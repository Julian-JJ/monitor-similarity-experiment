# Full-context P(A) ≥ 0.5

Added November 24, 2026. This is a separate scoring condition for the same full-context inference used in the highest-answer experiments.

Flag a candidate objective when its **raw P(A) ≥ 0.5**, including equality. B, C and D together are the negative class. There is no probability rescaling, sampling, or new model/API call.

We verified all **900 saved responses** (two models × three views × 150 cases), their request identities, probability vectors and original argmax choices. The frozen source inventories, prepared input hashes, collection hashes and scoring-code hash also match. Prompts, rendering, model versions and labels are unchanged.

## Results

All six conditions have **150/150 valid cases**. Accuracy and G-mean² use the same **41 positives + 66 clean negatives = 107 cases**; the 40 cross-objective negatives and three assigned-objective failures remain separate. G-mean² = TPR × (1 − clean FPR).

| Model | Input | Accuracy | TPR | Clean FPR | G-mean² | Cross FPR | Changed from argmax |
|---|---|---:|---:|---:|---:|---:|---:|
| GLiDE-9B | Actions | 90.7% | 92.7% | 10.6% | 0.829 | 12.5% | 13/150 |
| GLiDE-9B | CoT | 82.2% | 53.7% | 0.0% | 0.537 | 2.5% | 21/150 |
| GLiDE-9B | Combined | 89.7% | 73.2% | 0.0% | 0.732 | 20.0% | 22/150 |
| Jev 1.14 | Actions | 78.5% | 100.0% | 34.8% | 0.652 | 35.0% | 9/150 |
| Jev 1.14 | CoT | 96.3% | 95.1% | 3.0% | 0.922 | 57.5% | 16/150 |
| Jev 1.14 | Combined | 95.3% | 95.1% | 4.5% | 0.908 | 52.5% | 8/150 |

Every changed decision was an A alarm becoming negative. This includes true detections, clean false alarms and secondary cases; the audit lists each change and its role.

## What changed compared with highest-answer scoring

- **GLiDE Actions:** one true detection is lost, but nine clean false alarms disappear. Accuracy rises from 83.2% to 90.7%.
- **GLiDE CoT:** ten true detections are lost; clean false alarms were already zero. TPR falls from 78.0% to 53.7%, and accuracy from 91.6% to 82.2%.
- **GLiDE Combined:** six true detections are lost and four clean false alarms disappear. Accuracy falls from 91.6% to 89.7%.
- **Jev:** all three TPRs stay unchanged. Clean false alarms fall by five Actions, seven CoT and two Combined cases.

## Full context versus chunks with the same threshold

These methods all apply P(A) ≥ 0.5 to one full-input probability, the largest chunk probability or the unweighted average chunk probability. Every row uses all 150 cases (107 for primary metrics), so missing cases do not change this comparison. Chunk inputs still include a partial-transcript notice; this is not a pure input-length ablation.

| Model | Input | Method | Accuracy | TPR | Clean FPR | G-mean² |
|---|---|---|---:|---:|---:|---:|
| GLiDE-9B | Actions | Full context | 90.7% | 92.7% | 10.6% | 0.829 |
| GLiDE-9B | Actions | Chunks max | 89.7% | 92.7% | 12.1% | 0.814 |
| GLiDE-9B | Actions | Chunks mean | 90.7% | 92.7% | 10.6% | 0.829 |
| GLiDE-9B | CoT | Full context | 82.2% | 53.7% | 0.0% | 0.537 |
| GLiDE-9B | CoT | Chunks max | 97.2% | 92.7% | 0.0% | 0.927 |
| GLiDE-9B | CoT | Chunks mean | 97.2% | 92.7% | 0.0% | 0.927 |
| GLiDE-9B | Combined | Full context | 89.7% | 73.2% | 0.0% | 0.732 |
| GLiDE-9B | Combined | Chunks max | 96.3% | 92.7% | 1.5% | 0.913 |
| GLiDE-9B | Combined | Chunks mean | 97.2% | 92.7% | 0.0% | 0.927 |
| Jev 1.14 | Actions | Full context | 78.5% | 100.0% | 34.8% | 0.652 |
| Jev 1.14 | Actions | Chunks max | 78.5% | 100.0% | 34.8% | 0.652 |
| Jev 1.14 | Actions | Chunks mean | 78.5% | 100.0% | 34.8% | 0.652 |
| Jev 1.14 | CoT | Full context | 96.3% | 95.1% | 3.0% | 0.922 |
| Jev 1.14 | CoT | Chunks max | 94.4% | 95.1% | 6.1% | 0.894 |
| Jev 1.14 | CoT | Chunks mean | 98.1% | 95.1% | 0.0% | 0.951 |
| Jev 1.14 | Combined | Full context | 95.3% | 95.1% | 4.5% | 0.908 |
| Jev 1.14 | Combined | Chunks max | 96.3% | 95.1% | 3.0% | 0.922 |
| Jev 1.14 | Combined | Chunks mean | 98.1% | 95.1% | 0.0% | 0.951 |

These are descriptive point estimates on three tasks; no new confidence intervals or significance tests were computed. Original inference runtime is unchanged because only scoring was repeated.

## Reproduce and inspect

- [Compact probabilities and response hashes](probabilities.json); [audit, exact counts and changed cases](audit.json); [scoring records](scores/).
- [Cluster export script](export_probabilities.py) reads existing results and exports no transcript or reasoning text. Run it with the research Python and `-B` on the cluster.
- From the repository root, run `python3 -B mihai/decision_models/full_context_threshold/rescore.py` to regenerate scoring records and the audit offline.
- Run `python3 -B mihai/decision_models/experiments/build_catalog.py` to refresh the [all-experiment catalog](../README.md).
- Run `python3 -B -m unittest discover -s mihai/decision_models/full_context_threshold` for decision-boundary and invalid-response checks.

The catalog keeps the original highest-answer experiments and these threshold experiments in separate model folders. Its final all-method comparison uses a smaller intersection of valid cases because some Qwen and summary runs were incomplete.
