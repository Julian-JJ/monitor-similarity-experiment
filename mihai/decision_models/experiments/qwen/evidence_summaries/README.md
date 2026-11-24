# Qwen3-32B — evidence summaries

Create the common summary input used by the GLiDE and Jev summary experiments.

## How we ran it

Greedy Qwen, thinking enabled, separately summarizes every shared chunk. The instruction requests at most 350 words, relevant evidence and uncertainty, and no A–D verdict. Each final monitor sees all summaries in order.

| Input | Valid summaries | Truncated summaries | Complete final inputs |
|---|---:|---:|---:|
| Actions | 184/184 | 0 | 150/150 |
| CoT | 1,243/1,256 | 13 | 141/150 |
| Combined | 1,381/1,394 | 13 | 138/150 |

All 26 failures reached 16,768 output tokens. They block 21 case/view combinations. This experiment produces summaries, not classification accuracy. Their usefulness is measured in the two downstream experiments. Qwen’s 6:46:08 job also ran the greedy baseline; that wall time cannot be assigned to summaries alone.

Sources: [audit.json](../../../summary-results-20261124/audit.json) · [prompts.py](../../../variants/prompts.py)
