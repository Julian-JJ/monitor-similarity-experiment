# Full GLiDE CoT results

Completed and audited: **75 rollouts, 150 objective checks, zero failed checks**.
All full inputs were processed without hierarchical summaries. The final audit
verified input and configuration hashes, reported token counts, deterministic
sampling and score calculations.

| Decision method | Detection rate | Clean-control false alarms | G-mean² |
|---|---:|---:|---:|
| Four sampled answers | 62.8% (103/164) | 1.9% (5/264) | 0.616 |
| Highest-probability answer | 78.0% (32/41) | 0.0% (0/66) | 0.780 |

The four sampled answers come from one probability vector per check, using
temperature 0.6, top-p 0.9 and seed 0. They are scored individually, as in the
actions evaluation. These are pooled results across both target objectives.
False alarms in this table use the baseline's clean-control group; the separate
cross-objective and own-objective-failure groups are in the metric JSON files.
Zero observed false alarms does not establish a zero population false-alarm rate.

For comparison, the sampled actions evaluation achieved 94.5% detection,
23.5% clean-control false alarms and G-mean² 0.723. On these data, CoT is less
likely to flag both positive and clean examples. This comparison reports observed
rates, not a test of statistical significance.

The original job, **33509938**, exited unexpectedly after saving 108 valid
checks. The cause remains unknown. Restart **33512196** preserved those files
byte-for-byte, completed the other 42, and exited `0:0` at **21:01 on 2026-11-15,
America/New_York**. The original job used 27:13 and the restart 39:00, totaling
66:13 of GPU allocation. Successful calls took 65:01.5, averaging 26.0 seconds.

The restart logged six GPU-allocation warnings but returned all expected results.
Peak allocated memory was 50.5 GiB and reserved memory reached 93.1 GiB on the
Blackwell GPU. The warnings do not establish what caused the original exit.

- [Final audit](final-audit.json) and [completion summary](summary.json).
- [Sampled scores and intervals](sampled-metrics.json).
- [Highest-probability scores and intervals](greedy-metrics.json).
- [Run configuration and submission records](../glide-cot-20261115-c8f6c4e8.json).
- [Saved result checksums](result-checksums.json).

Raw inputs and detailed decisions remain at
`$PROJECT/mihai/decision_models/runs/glide-cot-20261115-c8f6c4e8/`.
The local compact records contain verdicts and identifiers, not reasoning text.
