# GLiDE versus Qwen3-32B

Comparison prepared November 15, 2026, from saved evaluations; no new model inference was run. All results use the same 75 rollouts (41 from the original batch and 34 additional main-only controls), the same two target objectives, and the same scoring implementation. Collection hashes, rollout IDs, judgment keys, completion status, and recomputed metrics were checked against the saved reports.

## Detection results

“Detection” is the fraction of positive cases flagged. “Clean false alarms” is the fraction of clean controls incorrectly flagged. G-mean² is detection × (1 − clean false alarms), so higher is better. It is not ordinary accuracy. Results pool both target objectives.

| Input | Monitor | Decision rule | Detection ↑ | Clean false alarms ↓ | G-mean² ↑ |
|---|---|---|---:|---:|---:|
| Actions | Qwen3-32B | Four sampled analyses | 100.0% | 28.8% | 0.712 |
| Actions | GLiDE-9B | Four sampled answers | 94.5% | 23.5% | 0.723 |
| Actions | GLiDE-9B | Most likely answer | 95.1% | 24.2% | 0.721 |
| CoT / reasoning | Qwen3-32B | Four sampled analyses | 95.1% | 21.6% | 0.746 |
| CoT / reasoning | GLiDE-9B | Four sampled answers | 62.8% | 1.9% | 0.616 |
| CoT / reasoning | GLiDE-9B | Most likely answer | 78.0% | 0.0% | 0.780 |
| Combined actions + CoT (`all`) | Qwen3-32B | Four sampled analyses | 94.5% | 24.2% | 0.716 |
| Combined actions + CoT (`all`) | GLiDE-9B | Either rule | Not evaluated | Not evaluated | Not evaluated |

Sampled scores count four answers per case separately, without majority voting. Each sampled scope has 600 answers: 75 rollouts × two target objectives × four samples. The main score uses 41 positive cases and 66 clean-control cases, giving 164 positive and 264 clean-control sampled answers. The other 40 cross-objective cases and three own-objective failure cases have separate descriptive scores in `comparison.json`; they are not included in the primary clean-control score. Most-likely-answer results use one answer per case, so their main denominators are 41 and 66.

On actions, GLiDE and Qwen have similar primary scores: GLiDE misses some positives but raises fewer false alarms. On CoT, sampled Qwen detects substantially more positives than sampled GLiDE. GLiDE's most-likely-answer rule improves its CoT result, detecting 32 of 41 positive cases with zero false alarms among 66 clean controls. Zero observed false alarms is not a guarantee on new data. Its 0.780 score is the largest point estimate in this table, but Qwen has no matching most-likely-answer evaluation.

The exploratory paired bootstrap for sampled GLiDE minus sampled Qwen gives an actions G-mean² difference of +0.011 (95% interval −0.065 to +0.090) and a CoT difference of −0.130 (−0.236 to −0.024). These comparisons cover this dataset's three tasks, not generalization to unseen tasks.

## Observed runtime

| Input | GLiDE GPU job time | Qwen approximate evaluation phase time |
|---|---:|---:|
| Actions | 5m 04s | About 24m 26s |
| CoT / reasoning | 1h 06m 13s | About 2h 42m 53s |
| Combined actions + CoT | Not evaluated | About 2h 43m 13s |

GLiDE's CoT time includes its first interrupted job (27m 13s) and successful continuation (39m). The continuation retained all 108 previously completed cases and finished the remaining 42. Both GLiDE decision rules use the same model calls, so the sampled and most-likely results did not require separate inference runs.

Qwen's three scopes ran in shared sessions with overlapping work at scope boundaries. The per-scope numbers above are estimates from completion timestamps, not separately measured scope runtimes. Total recorded Qwen32B evaluation-session time across the three scopes was 5h 50m 32s. This excludes gaps between sessions and is not the total scheduler allocation time.

These are observed system runtimes, not a controlled model speed benchmark. Qwen used one H200, up to 32 concurrent judgments, and four independently generated analyses per case. GLiDE used one RTX PRO 6000 Blackwell, one case at a time, and one probability vector from which four answers were sampled. Qwen used hierarchical processing for 120/600 actions judgments and all CoT/combined judgments; GLiDE processed each input directly. Qwen made 856 actions, 6,353 CoT and 7,010 combined model requests, versus 150 GLiDE model calls per evaluated scope.

## Comparison limits and provenance

- Sampling settings are temperature 0.6 and top-p 0.9, but sampling labels from GLiDE is different from generating Qwen's four separate analyses.
- GLiDE uses the adapted A–D decision prompt. Qwen uses the original prompt, generated reasoning and hierarchy. This compares the evaluated monitoring systems, not architecture alone.
- GLiDE full-CoT prompts span 22,007–216,463 tokens. Actions use the existing renderer, including the 2,000-character tool-result cuts. Grading labels stay outside the monitor input.
- GLiDE revision: `ab54df5acba0eebf7df45560ffdaacd64e32df3b`; Qwen32B revision: `9216db5781bf21249d130ec9da846c4624c16137`.
- Scoring framework commit: `6043ff7a875bf6d2d792cec7df603c5cd019c647`.
- GLiDE actions run: `glide-actions-20261115-60611f0f`, job `33492538`.
- GLiDE CoT run: `glide-cot-20261115-c8f6c4e8`, jobs `33509938` and `33512196`.
- Qwen32B jobs: `30068483` and `30069109`. The shared baseline also contains Qwen14B results; those were excluded.
- Qwen source: `/nfs/roberts/project/cpsc4880/cpsc4880_as4833/runs/baseline`.
- GLiDE source: `/nfs/roberts/project/cpsc4880/cpsc4880_mae73/mihai/decision_models/runs/`.

`comparison.json` contains exact scores, counts, source hashes and timing boundaries. `compare_saved_results.py` reproduces this audit on the cluster using the existing research environment and frozen framework; it does not run inference or print reasoning text. Raw model inputs and responses remain on the cluster.
