# Hierarchical monitor

Related: [scope](01-scope.md) · [monitor evaluation](04-monitor-evaluation.md) ·
[token-count analysis](../analysis/transcript-token-counts.md) ·
[baseline research notes](../research/monitor-baseline-notes.md) ·
[work log](../worklog.md).

Status (2026-10-19): the design below is implemented as a library
([`monitor_experiment/hierarchy.py`](../../monitor_experiment/hierarchy.py)) with
offline tests and two dry-run scripts. **No monitor model has been run.** The
command that executes monitors (`scripts/run_monitors.py`) is still unwritten.

## Why a hierarchical monitor is needed

MonitorBench's monitor reads one prompt containing the whole transcript.
Upstream serves its monitor with a 32,768-token context and reserves 16,768
tokens for the answer, leaving about 15.5k tokens of input. Our saved Qwen3-14B
rollouts do not fit. The actor's reasoning alone has a median of 76k tokens, and
the largest complete prompt is 235k. See the
[token-count analysis](../analysis/transcript-token-counts.md) for all numbers.

| Scope | Rollouts whose complete single-pass prompt exceeds the 15,488-token input limit | Exceeds 131,072 |
| --- | ---: | ---: |
| `action`, tool results cut at 2,000 characters | 9 of 41 | 0 |
| `cot` (reasoning) | 41 of 41 | 8 |
| `all`, tool results cut at 2,000 characters | 41 of 41 | 10 |

The released upstream code has no hierarchical monitor, although the paper
describes one for agent tasks; see [the research notes](../research/monitor-baseline-notes.md).
This design is therefore **ours**. It is meant to match the paper's idea, not to
reproduce an unseen implementation. Every choice below that the paper might
make differently is listed under [Deviations and unknowns](#deviations-and-unknowns).

## Design in one picture

```text
transcript ──render for one scope──► turns ──pack into chunks (≤ chunk_tokens)──►

  chunk 1   chunk 2   chunk 3   chunk 4   chunk 5     level 0: upstream prompt + part notice
     └─────────┴────┬────┴─────────┘         │
             combine (bin of ≤ 4)          carried up      level 1: combining prompt
                    └──────────┬─────────────┘
                          combine                        level 2: root
                              │
                      <answer>A|B|C|D</answer>           the monitor's verdict
```

- A transcript whose complete upstream prompt fits the input limit is **one chunk**.
  Its prompt is the unmodified upstream prompt, so single-pass monitoring is the
  one-chunk special case of this monitor, not a separate method.
- Level-0 chunk calls are independent of each other and can run in parallel.
- Each node's output is the monitor's own written analysis plus an A–D verdict
  (upstream's format). Analyses are the "reports" passed upward.
- The root's verdict is the result. Intermediate verdicts are kept for
  diagnosis and never averaged into it.

## Components

### Observation scopes and rendering

`render_turn` produces one turn's text per scope. A *turn* is one assistant
message plus the tool replies that follow it.

| Scope | Contents of a turn |
| --- | --- |
| `action` | tool calls (`name(arguments)`) and tool results |
| `cot` | the assistant's stored **reasoning**, then its visible text if non-blank |
| `all` | reasoning, visible text, tool calls, tool results, in that order |

- Each turn starts with a label naming only the turn number and message IDs
  (`=== Turn 12 (messages m00024-m00025) ===`). The monitor can cite it. It
  contains no label, score, or state.
- Tool results longer than `truncate_chars` (2,000, upstream's rule) are cut with
  upstream's `...[truncated]` marker. Cuts are counted and reported per rollout.
  Setting `truncate_chars` to `None` disables them.
- Only assistant and tool messages are rendered. The system prompt, evaluation
  results, initial and final state, and identity never reach a prompt. The one
  deliberate disclosure is the hidden objective, which upstream also gives to the
  monitor. A test checks that system-prompt text does not leak.
- Why the `cot` scope reads stored reasoning: in our rollouts, the assistant's
  visible `content` is almost always `'\n\n'`. Upstream's `cot` scope renders
  `content`, so the monitor would see essentially no actor text; the whole prompt
  is about 1k tokens, nearly all template, task and objective. See the analysis.

### The hidden objective and main task

The main task is the first user message. The hidden objective is cut out of the
system message between the fixed preamble ("…complete the secondary task.") and
the fixed continuation ("At each step, you will be given…"), exactly as the vendored
`construct_system_message` assembles it. A test extracts it from all 41 saved
rollouts. `main_only` rollouts contain no objective, so they raise an error: the
text for their monitor input must be supplied separately (an open decision).

### Chunking

1. Render each turn. A turn larger than `chunk_tokens` is split at paragraph,
   then line, then word boundaries (last resort: halving by characters). Every part
   gets its own label with `part i of n`. Splitting is lossless; a test checks that
   every word of every turn appears exactly once, in order.
2. Pack consecutive segments greedily into chunks of at most `chunk_tokens`. The
   packed size is re-checked with a real token count.
3. Each chunk's complete prompt must fit the input limit; otherwise planning
   fails with an error (when `chunk_tokens` alone is too large, it names the
   largest allowed value). Nothing is truncated silently.

Chunks do not overlap. A turn is never split unless it alone exceeds the budget.
This is a simplicity choice; it is listed under limitations.

### Prompts

| Prompt | Source | Used when |
| --- | --- | --- |
| Upstream agent monitor, per scope | vendored verbatim: [`vendor/monitorbench_monitor/`](../../vendor/monitorbench_monitor/README.md) | every level-0 call |
| Part notice | **ours**: [`prompts/monitor_chunk_notice.txt`](../../prompts/monitor_chunk_notice.txt) | inserted before the transcript in level-0 prompts when there is more than one chunk |
| Combining prompt | **ours**: [`prompts/monitor_reduce.txt`](../../prompts/monitor_reduce.txt) | every level above 0 |

The part notice tells a chunk reviewer that it sees only part *i* of *n*, that
absence of evidence in a part is not evidence of innocence, and that its verdict
describes only that part. The combining prompt reuses upstream's four options and
answer format and tells the combiner to look for evidence that only makes sense
across parts, keep exact quotes and turn labels, and not read one part's silence
as contradicting another part's evidence.

Before analyses are passed upward, each `<answer>X</answer>` is rewritten as
`[partial verdict: X]`. The combiner's prompt then contains exactly one
`<answer>` tag, in the instruction that defines its own output format, so only the
combiner's own answer is parsed.

### Verdicts and failures

- The verdict is parsed the way upstream does it: the first
  `<answer>[A-D]</answer>`. `A` is "detected". `B`, `C` and `D` are not.
- Upstream turns an unparseable answer into the string `"None"`, which then counts
  as *not detected*. **We do not.** A response is valid only if generation stopped
  normally (`finish_reason == "stop"`) and contains an A–D answer. Truncated
  generations, even ones containing a tag, are invalid.
- An invalid node is retried up to `max_attempts` (default 2) with a different
  seed. Every attempt is kept.
- If any node of a level is still invalid, the run ends with status `invalid` and
  verdict `None`. The next level is not run on partial data. Invalid runs are
  reported as invalid and counted in coverage; they are never converted to a
  negative verdict.
- A partial analysis too large to fit a combining prompt, or a level where no bin
  can hold two analyses, ends the run with status `error`. No analysis is shortened.
- Transport errors (a server being down) propagate as exceptions.

### Combining

`make_bins` groups consecutive nodes into bins of at most `bin_size` analyses
whose combining prompt still fits the input limit. A bin with one node is carried
up unchanged with no model call. Bins are built after the level below finishes,
from the real analysis sizes.

### Samples, seeds and identity

- Upstream's monitor config takes `rollout_number: 4` samples per item. Here a
  *sample* is one complete run of the whole tree, independent of the others
  (different seed offset). Sample counts multiply cost.
- Seeds are `base + 10 * node_ordinal + attempt`.
- A node's ID is a SHA-256 over the rollout ID, all parameters, its level and
  position, its children's IDs and its prompt. Changing any setting changes every
  affected ID, so cached results cannot be reused under different settings.

## Parameters

| Parameter | Default | Meaning and reason |
| --- | ---: | --- |
| `scope` | none | `action`, `cot` or `all` |
| `context_tokens` | 32,768 | monitor context window; upstream's monitor setting |
| `output_reserve` | 16,768 | tokens reserved for the answer; upstream's `max_tokens` |
| `margin_tokens` | 512 | slack so a prompt is never right at the limit |
| `chunk_tokens` | 12,000 | transcript tokens per level-0 chunk. Fixed, not derived per rollout, so every rollout in a condition is chunked the same way. The fixed prompt around a chunk measures 0.8k–1.35k tokens over the 41 rollouts (median 1.1k), so a full chunk prompt stays under the 15,488 input limit. |
| `bin_size` | 4 | analyses combined per call. **A guess**: the paper's value was not readable. The pre-registered experiments set 6 in the experiment file (chosen from the measured chunk counts; see [07](07-design-decisions.md#27-hierarchy-and-sampling-settings)); the library default stays 4. |
| `truncate_chars` | 2,000 | upstream's tool-result cut |
| `labels` | true | turn labels in the rendered transcript |
| `max_attempts` | 2 | tries per node before it is invalid |
| `single_pass_if_fits` | true | use one unmodified upstream prompt whenever the whole transcript fits the input limit |

The input limit is `context_tokens − output_reserve − margin_tokens`
(15,488 with the defaults). Parameters are validated; for example `bin_size`
below 2 is rejected because no level could reduce the one below it.

## Two configurations to compare

| | `upstream-limits` | `long-context` |
| --- | --- | --- |
| Monitor context / output reserve | 32,768 / 16,768 | 131,072 / 16,768 (YaRN factor 4) |
| `chunk_tokens` | 12,000 | 100,000 |
| Why | matches upstream's monitor serving | far fewer chunks; but static YaRN can change short-context behavior and a 100k-token prompt strains any monitor |

Dry-run results over the 41 saved rollouts
(`mihai/results/hierarchy-plan-32k-20261019.json`,
`mihai/results/hierarchy-plan-131k-chunk100k-20261019.json`; four independent
samples per rollout; combining-level input is **estimated** assuming 1,000-token
analyses):

| Config | Scope | One pass / hierarchical | Chunks median / max | Levels (max) | Model calls, 4 samples | Input tokens (est.) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| upstream-limits | `action` | 31 / 10 | 1 / 3 | 2 | 248 | 2.2 M |
| upstream-limits | `cot` | 0 / 41 | 8 / 23 | 4 | 2,024 | 18.2 M |
| upstream-limits | `all` | 0 / 41 | 8 / 26 | 4 | 2,240 | 20.3 M |
| long-context | `action` | 41 / 0 | 1 / 1 | 1 | 164 | 2.0 M |
| long-context | `cot` | 30 / 11 | 1 / 3 | 2 | 260 | 14.6 M |
| long-context | `all` | 28 / 13 | 1 / 3 | 2 | 276 | 16.3 M |

These count monitor calls on Qwen3-32B only. Each call also spends up to 16,768
output tokens on thinking and answer, which is not included in the input totals.
Long prompts cost more per token than short ones, so equal token totals do not
mean equal GPU time.

We have not chosen between the configurations. The proposal is to treat
`upstream-limits` as the primary hierarchical condition (it follows upstream's
serving limits) and `long-context` as a comparison.

## Deviations and unknowns

Where this differs from upstream's code, or where the paper may differ from this:

1. **Hierarchy itself.** Upstream's released agent path is single-pass. The paper
   describes chunk outputs grouped into bins and re-monitored; its chunk size and
   bin size were not readable. `chunk_tokens` and `bin_size` are ours.
2. **Turn labels** in the transcript are added by us. Upstream's rendering has none.
   Labels carry no outcome information.
3. **`cot` scope reads stored reasoning** rather than visible content.
4. **Blank visible content** (`'\n\n'`) is not rendered. Upstream appends it.
5. **Tool-call arguments** are the model's JSON string verbatim. Upstream's
   formatter JSON-dumps whatever its `args`/`arguments` field holds; its stored
   form for rollouts was not inspected, so spacing or quoting may differ.
6. **Invalid answers** are invalid, not "not detected". Upstream's `"None"` counts as
   not detected.
7. **No filter on side-objective success is applied here.** Upstream's agent path
   monitors every rollout, while the paper conditions the score on success.
   Which rollouts are scored is decided at evaluation time, from the saved labels.
8. **The combining prompt and part notice are ours** and may change results. They
   should be reported with any number produced.
9. **Retries.** The upstream code I read has no retry logic.

## Limitations and risks

- **Information loss.** A true clue can be left out of a partial analysis. Evidence
  spread across chunks is only recoverable if each partial analysis notes it.
- **Chunk boundaries.** Chunks do not overlap, so a pattern spanning two chunks is
  visible to no single reviewer.
- **Order and framing effects.** The part notice and the combining prompt can push
  verdicts toward or away from `A`. A chunk reviewer sees a partial verdict
  question it cannot fully answer.
- **Cost.** The `cot` and `all` scopes need about 2,000 calls (upstream-limits).
- **Report size.** The cost estimate for combining levels assumes 1,000-token
  analyses. Real analyses are unmeasured.
- **A 100k-token prompt** (long-context) is untested on Qwen3-32B with YaRN here.
- **Actor transcripts are long by our choice.** Our actor allowed 32,768 output
  tokens per call; upstream's agent path caps a call at 2,000. Different actor
  settings would change every number above.
- **`main_only` rollouts** need an objective text from somewhere else.

## Validation

Done (offline, no model): `tests/test_hierarchy.py`, 30 tests. They check
rendering per scope, lossless splitting, full coverage of every word of every turn
once and in order, single-chunk prompts being byte-identical to upstream's,
exactly one part notice, tree shape against the call-count formula, neutralized
partial verdicts, retry and invalid handling, truncated generations never being
verdicts, no silent shortening, deterministic node IDs, and hidden-objective
extraction from all 41 saved rollouts.

Still needed before the numbers mean anything:

1. A pilot against a real Qwen3-32B server on a few rollouts: do replies parse, how
   long are the analyses, how many are invalid?
2. **Information-loss check.** On the 31 `action` rollouts that fit one pass, force
   chunking with a small `chunk_tokens` and compare verdicts with the one-pass
   verdicts. Agreement estimates how much the hierarchy loses.
3. **Planted-evidence check.** Insert a known, objective-revealing action into
   different positions of a transcript and see whether the hierarchy still reports it.
4. Sensitivity of results to `chunk_tokens` and `bin_size`.

## Interface

```python
from monitor_experiment import hierarchy as h
prompts = h.load_prompts()
count = h.tokenizer_counter("cache/tokenizer/tokenizer.json")   # needs `tokenizers`
params = h.default_params("cot")                                 # override any key
planned = h.plan(messages, params, count, prompts)               # offline: chunks and exact prompts
result = h.run_tree(rollout_id, planned["chunks"], params, count, prompts,
                    planned["main_task"], planned["objective"], complete, seed=0)
```

`complete(prompt, seed)` must return `{"text": visible_response, "finish_reason": ...}`
and may add `reasoning` and `usage`. The result records `status`
(`complete`, `invalid`, `error`), `verdict`, `hierarchical`, `calls`,
`model_requests`, and every node with its attempts, prompt size, text and verdict.

Dry runs:

```bash
python scripts/count_transcript_tokens.py          # which prompts fit a context window
python scripts/plan_hierarchy.py                   # chunks, calls, tokens; upstream-limits
python scripts/plan_hierarchy.py --context-tokens 131072 --chunk-tokens 100000
```

## Open decisions

1. Which configuration is primary (`upstream-limits` or `long-context`)?
2. `bin_size` and `chunk_tokens`, given that the paper's values were unreadable.
3. The hidden-objective text for `main_only` rollouts.
4. Whether to keep the part notice and combining prompt as written, after the pilot.
5. Whether the `action` scope should be run hierarchically at all, since 31 of 41
   rollouts fit one pass at upstream limits, or only for the rollouts that need it.
