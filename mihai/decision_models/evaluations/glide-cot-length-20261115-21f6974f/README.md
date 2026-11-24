# GLiDE reasoning length pilot results

Job **33507318** completed on 2026-11-15 (America/New_York) in **36:27**, exit
`0:0`, on one NVIDIA RTX PRO 6000 Blackwell Server Edition. The audit verified
all **70 expected calls**, with zero failures or missing measurements, and
confirmed that every submitted input was processed without silent truncation.

The pilot tests ten sizes using prefixes of one real reasoning transcript and
four synthetic controls per size. At the largest size, the real transcript is
complete. It is not a full accuracy evaluation of the dataset.

| Full prompt tokens | Warm call, seconds | Peak allocated, GiB | Peak reserved, GiB |
|---:|---:|---:|---:|
| 2,000 | 0.16 | 15.1 | 16.7 |
| 8,000 | 0.78 | 16.1 | 16.7 |
| 16,000 | 1.77 | 17.5 | 17.6 |
| 32,000 | 4.43 | 20.1 | 20.6 |
| 40,000 | 6.09 | 21.4 | 23.7 |
| 64,000 | 12.37 | 25.4 | 28.9 |
| 96,000 | 23.88 | 30.7 | 33.9 |
| 128,000 | 40.63 | 35.9 | 40.2 |
| 192,000 | 84.15 | 46.5 | 52.6 |
| 216,463 | 105.48 | 50.5 | 62.5 |

Warm time averages two calls after the first call in a fresh model process.
It includes tokenization and synchronized GPU work, excluding model loading.
Peak allocation includes model weights. Reserved memory includes PyTorch's
allocator cache; neither figure includes all driver overhead. The longest
first call took 115.38 seconds. Full values are in [summary.json](summary.json).

![Runtime, memory, and evidence checks](length-pilot.png)

All **40/40 highest-probability control decisions** were correct: three positive
examples with evidence near the beginning, middle or end, plus one clean example
at each size. All **160/160 sampled control answers** were also correct using
temperature 0.6, top-p 0.9 and four seeded draws per probability vector.
Those draws are not 160 independent model executions.

There is a measurable change in the probabilities despite the correct decisions.
For the middle-evidence control, P(A) falls from **0.968 at 2k** to **0.712 at
216k**. These are model probabilities, not calibrated probabilities of correctness.
The evidence is explicit and the background is repetitive synthetic flight
planning, so this establishes a narrow capability, not general monitoring accuracy.

The real dataset contains **75 rollouts and 150 objective prompts**, ranging
from **22,007 to 216,463 tokens**, with median **68,542**. All fit within the
tested maximum. We recommend testing the full real CoT inputs directly next,
without hierarchical summaries, to measure accuracy. Interpolation from the
measured timings predicts **58.5 minutes of inference** for the 150 cases on
this GPU, excluding loading, compilation, scoring and other overhead; this is
an estimate rather than an actual evaluation. Combined inputs remain untested.

The model revision, BF16 precision, environment and weights stayed fixed; only
the request-length guard increased. Exact inputs, full decision records and
the audit script remain on the cluster under
`$PROJECT/mihai/decision_models/runs/glide-cot-length-20261115-21f6974f/`.
Frozen submitted code is under
`$PROJECT/releases/glide-cot-length-20261115-21f6974f/`.

See [the audit](final-audit.json), [run record](../glide-cot-length-20261115-21f6974f.json),
[length inventory](lengths.json), [runtime estimate](runtime-projection.json),
and [readable pilot code](../../long_context/README.md).
