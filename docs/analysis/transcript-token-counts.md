# Transcript token counts

Date: 2026-10-19. Question: do the saved Qwen3-14B rollouts fit a monitor's
context window when monitored in a single pass, or is a
[hierarchical monitor](../plan/05-hierarchical-monitor.md) needed?

**Answer:** for the `cot` and `all` scopes, yes. For `action`, most fit.

## Method

- Data: the 41 complete original rollouts (`rollouts_original_clean/`, copied
  from the cluster on 2026-10-19; see the [work log](../worklog.md)).
- Tokenizer: `tokenizer.json` of the pinned Qwen3-14B revision
  (`40c069824f4251a91eefaf281ebe4c544efd3e18`), copied from the cluster. Qwen3-32B,
  the upstream monitor model, uses the same tokenizer family.
- For each rollout and scope, the transcript is rendered with
  `monitor_experiment/hierarchy.py` (no turn labels, to match upstream's plain
  join), inserted into MonitorBench's unmodified agent monitor prompt together
  with the main task and hidden objective, and the **whole prompt** is counted.
- Command: `python scripts/count_transcript_tokens.py`.
  Output: [`mihai/results/transcript-token-counts-20261019.json`](../../mihai/results/transcript-token-counts-20261019.json)
  (per-rollout counts, per-task summaries).

Limits compared against:

| Limit | Tokens | Where it comes from |
| --- | ---: | --- |
| Input limit | 15,488 | upstream monitor: 32,768 context − 16,768 output reserve − 512 margin |
| 32k context | 32,768 | upstream's monitor `max_model_len` |
| 131k context | 131,072 | 32,768 extended with YaRN factor 4 |

## Results

Tokens of the complete single-pass prompt, 41 rollouts:

| Variant | Median | 95th pct | Max | Over 15,488 | Over 32,768 | Over 131,072 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `action`, tool results cut at 2,000 characters (upstream's rule) | 9,529 | 22,247 | 25,404 | 9 | 0 | 0 |
| `action`, tool results uncut | 26,007 | 45,553 | 60,921 | 39 | 6 | 0 |
| `cot`, visible assistant text only (what upstream renders) | 1,026 | 1,249 | 1,249 | 0 | 0 | 0 |
| `cot`, stored reasoning | 76,108 | 169,778 | 212,516 | 41 | 38 | 8 |
| `all`, tool results cut at 2,000 characters | 84,246 | 176,242 | 225,199 | 41 | 40 | 10 |
| `all`, tool results uncut | 104,621 | 196,145 | 234,989 | 41 | 41 | 12 |

By task (median / max prompt tokens; median turns):

| Task | n | Turns | `action` cut | `cot` reasoning | `all` cut |
| --- | ---: | ---: | ---: | ---: | ---: |
| `american_airlines_2` | 13 | 48 | 10,212 / 13,410 | 109,948 / 212,516 | 120,884 / 225,199 |
| `bank_transfer_2` | 13 | 33 | 5,787 / 7,677 | 101,674 / 209,307 | 106,441 / 213,280 |
| `spam_filter_update` | 15 | 29 | 16,167 / 25,404 | 44,689 / 58,116 | 63,228 / 82,265 |

## What this shows

1. **Reasoning dominates.** The actor's stored reasoning makes the `cot` prompt a
   median 8.0 times the size of the `action` prompt per rollout (range 1.7 to 41.8;
   task medians 2.7 for `spam_filter_update`, 9.7 for `american_airlines_2`, 17.6 for
   `bank_transfer_2`). Every `cot` and `all` prompt exceeds the upstream input limit,
   and 8 to 12 exceed even 131k.
2. **A longer context does not fully solve it.** At 131k, 8 (`cot`) or 10 (`all`,
   cut) of 41 rollouts still do not fit a single pass.
3. **`action` mostly fits.** With upstream's 2,000-character tool-result cut,
   32 of 41 fit the upstream input limit; none exceeds 32k. All 9 that do not are
   `spam_filter_update` rollouts. That task has the longest action transcripts but
   the shortest reasoning.
4. **Upstream's `cot` scope would be empty for our data.** The assistant's visible
   `content` is essentially `'\n\n'`; the thinking is stored separately as
   `reasoning`. Rendering `content` as upstream does leaves the monitor roughly
   1k tokens of prompt and no actor text. The `cot` scope must read `reasoning`.
5. **Why the transcripts are this long** is our actor configuration: it allowed
   32,768 output tokens per call, where upstream's agent path caps a call at 2,000
   (including thinking). The mean `cot` prompt is about 86.9k tokens per rollout.
   Whether upstream-sized caps would shrink this was not tested.
6. **The tool-result cut matters.** Without it, 39 of 41 `action` prompts exceed the
   upstream input limit (all 15 `spam_filter_update`, all 13 `american_airlines_2`,
   11 of 13 `bank_transfer_2`); with upstream's 2,000-character cut, only 9 do. The cut
   hides tool-output content from the monitor, which is a cost to detection that is
   not measured here. Runs record how many results were cut (248 across the 41
   rollouts under the default plan).

## Dry-run plan of the hierarchical monitor

`python scripts/plan_hierarchy.py` builds the exact level-0 prompts for all 41
rollouts and counts calls. These counts use turn labels (so they differ slightly
from the table above) and four independent monitor samples per rollout, as upstream
configures. Combining-level input is **estimated**, assuming 1,000-token analyses;
no monitor has been run to measure real analysis size.

| Configuration | Scope | One pass / hierarchical | Chunks median / max | Max levels | Model calls (4 samples) | Input tokens (est.) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| upstream-limits (32,768 / chunks of 12,000) | `action` | 31 / 10 | 1 / 3 | 2 | 248 | 2.2 M |
| upstream-limits | `cot` | 0 / 41 | 8 / 23 | 4 | 2,024 | 18.2 M |
| upstream-limits | `all` | 0 / 41 | 8 / 26 | 4 | 2,240 | 20.3 M |
| long-context (131,072 / chunks of 100,000) | `action` | 41 / 0 | 1 / 1 | 1 | 164 | 2.0 M |
| long-context | `cot` | 30 / 11 | 1 / 3 | 2 | 260 | 14.6 M |
| long-context | `all` | 28 / 13 | 1 / 3 | 2 | 276 | 16.3 M |

Results: [`hierarchy-plan-32k-20261019.json`](../../mihai/results/hierarchy-plan-32k-20261019.json),
[`hierarchy-plan-131k-chunk100k-20261019.json`](../../mihai/results/hierarchy-plan-131k-chunk100k-20261019.json).

Notes:

- `action` at upstream limits has 10 hierarchical rollouts here but 9 over the limit in
  the table above because turn labels add tokens.
- Two earlier experiments gave approximate numbers, now superseded: a partial
  cluster run (21 of 41 rollouts, stopped at the user's request; its output was
  not kept in the repository) and a first local pass that added a rough 600-token
  template allowance and counted the whole system prompt. The figures in this
  document are from the committed script and are exact for the tokenizer used.

## Caveats

- Counts apply to the saved original rollouts only. The planned `main_only`
  controls and any future rollouts will differ.
- Token counts use the Qwen3 tokenizer; other monitor families tokenize differently.
- The call and input-token totals for combining levels are estimates, as stated.
- Nothing here measures monitor quality, only whether a prompt fits.
