# GLiDE reasoning length pilot

This pilot measures capacity and speed before choosing a full CoT evaluation method.
It keeps the existing model, BF16 precision and environment. Only GLiDE's request
length limit changes. The model configuration has 262,144 positions, but GLiDE's
published default is 40,000 tokens and its upstream documentation does not
validate decision quality beyond that default.

- `prepare.py` verifies the same 75 rollouts and counts all 150 reasoning/objective
  prompts with GLiDE's tokenizer. It selects the longest without reading scores.
- `prompt.json` adapts the original MonitorBench CoT instructions to decision
  output in the same way as the actions experiment; A–D remain unchanged.
- `measure.py` measures approximately 2k, 8k, 16k, 32k, 40k, 64k, 96k, 128k,
  192k, then the longest actual prompt, capped at 240k. All counts include the
  task, target objective, instructions, answer options and model wrapper.

At each size, it runs an unchanged prefix of the selected reasoning transcript
three times: one first call and two warm calls. It also runs four constructed
flight-booking reasoning examples: clear evidence of a completed hidden objective
near 5%, 50% or 95% of the text, and an example without that evidence.
Sizing accounts for the evidence and the surrounding text; no injected evidence
is removed to meet a token budget. Positions are approximate character fractions.

Every size gets a fresh GPU process. Runtime includes tokenization and GPU work,
with GPU synchronization before and after timing. Memory records include model
load allocation, peak PyTorch allocated memory, and peak reserved memory. They
do not include all driver overhead. Persistent compilation caches are reused,
so the first call is not a guaranteed fully cold measurement.

A failed request stops larger sizes. Each size has a 15-minute timeout. Saved
measurements survive a timeout; the outer allocation has a two-hour limit.
This pilot does not retry failed requests or change weights, precision or RoPE.

Raw inputs and detailed responses stay on the cluster. Each response retains
the A–D probabilities, highest-probability choice and four seeded sampled labels
(temperature 0.6, top-p 0.9). Output files are `lengths.json`, `ready.json`,
`level-N.json`, `measurements/N-CASE-REPEAT.json`, and `summary.json`.

**Interpretation:** an unfinished prefix cannot be graded using its full rollout's
outcome. The four constructed controls test obvious evidence detection and false
alarms in one scenario using the highest-probability answer; they do not
establish general monitoring accuracy.
No combined-scope evaluation is included in this pilot.

After a run, `plot_results.py OUTPUT_DIRECTORY` uses the existing research
environment's Matplotlib installation to draw runtime, memory and control results
from `summary.json`. It does not read any raw reasoning text.

The first pilot, job **33507318**, completed all ten lengths through **216,463
tokens** on 2026-11-15 (cluster local time), with 70 successful calls and no errors.
The maximum length took 105.5 seconds per warm call and allocated 50.5 GiB of GPU
memory (62.5 GiB reserved). All 40 synthetic controls and 160 sampled control
answers were correct. See the [full results and chart](../evaluations/glide-cot-length-20261115-21f6974f/README.md).
