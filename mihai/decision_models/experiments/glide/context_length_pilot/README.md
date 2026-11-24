# GLiDE-9B — length, memory and runtime pilot

Check whether full-length reasoning fits in memory and whether simple evidence remains detectable as input length grows.

## How we ran it

Ten sizes from 2,000 to 216,463 tokens; prefixes of one real CoT prompt plus four synthetic controls at each size. Use BF16 on one Blackwell GPU; only the request-length guard changes.

| Prompt tokens | Warm seconds | Peak allocated GiB | Peak reserved GiB |
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

All 70 calls completed; 40/40 highest-option synthetic decisions and 160/160 sampled labels were correct. The repeated labels share inference. These explicit synthetic clues are not evidence of 100% real-rollout accuracy. The full pilot took 36:27; warm times exclude model loading. Memory is PyTorch allocated/reserved memory, not total system memory.

Sources: [summary.json](../../../evaluations/glide-cot-length-20261115-21f6974f/summary.json) · [final-audit.json](../../../evaluations/glide-cot-length-20261115-21f6974f/final-audit.json) · [length-pilot.png](../../../evaluations/glide-cot-length-20261115-21f6974f/length-pilot.png) · [measure.py](../../../long_context/measure.py)
