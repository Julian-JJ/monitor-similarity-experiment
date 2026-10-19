# Fingerprints and the freeze

Code: [`monitor_experiment/freeze.py`](../../monitor_experiment/freeze.py); entry point `scripts/freeze.py`; locks `prompts/prompts.lock.json` and
`configs/presence_rules.lock.json`. Tests: `tests/test_freeze.py`. Why: [07 section 2.8](../plan/07-design-decisions.md#28-prompts).

## Three separate things

| | What it covers | Why it is separate |
| --- | --- | --- |
| **Cell fingerprints** | the five prompt files (our chunk notice, combining prompt, plan prompt and plan block, and MonitorBench's vendored monitor prompt), `configs/tool_lists.json`, `configs/objectives.json`, the reference tokenizer | these decide what a monitor is asked and sees. They go into every **cell ID**, so editing any of them changes every affected cell and old results cannot be mistaken for new ones |
| **The freeze lock** (`prompts/prompts.lock.json`) | the cell fingerprints **plus** `configs/councils.toml` and `configs/comparisons.toml` (the pre-registered analysis definitions) | the analysis definitions must not change after results exist, but they do not change what a monitor says, so they are in the lock and **not** in cell IDs |
| **The presence-rules lock** (`configs/presence_rules.lock.json`) | `configs/presence_rules.json` | the rules must stay editable until the human agreement check passes (after the pilot), so they cannot share the prompts' freeze |

The split matters in practice. An earlier version put the councils, comparisons and presence rules into cell IDs; editing a comparison or revising a presence rule would then have
invalidated every monitor output, hours of GPU time, although none of them affects a monitor's reply. A test now checks that editing an analysis file changes the lock but not one cell ID
([amendment A5](../plan/07-design-decisions.md#amendment-log)).

## States of the prompt lock

| Status | Meaning | Effect |
| --- | --- | --- |
| missing | no lock file | the runner records this in the manifest and continues |
| `draft` | wording may still change | a mismatch is reported, not fatal; the manifest records `prompts_status: draft` and every report warns |
| `frozen` | wording is fixed for confirmatory runs | a mismatch **stops the runner** with the list of changed files |

## Workflow

1. Write prompts. `python scripts/freeze.py write --status draft` records the current state.
2. Run the format-only pilot (`configs/experiments/pilot-format-only.toml`, `SCORE=0`). Judge it by `scripts/pilot_summary.py` only. Wording changes are allowed only to fix **format** failures (unparseable
   replies, truncation, over-long plans, refusals) and are logged.
3. `python scripts/freeze.py write --status frozen`, then commit the lock. From then on any change is an **amendment** ([07 amendment log](../plan/07-design-decisions.md#amendment-log)).
4. `python scripts/freeze.py status` shows the status and any differing file (exit status 1 if frozen and violated, or missing).
5. The presence rules follow their own path: `freeze.py rules-write --status draft` now; `--status frozen` once two annotators' agreement and the spot-check recall pass
   ([presence-labels](presence-labels.md)); `freeze.py rules-status` to check.

## Current state

* **Prompt lock: `frozen`** since the format-only pilot found no format failure (job 30068179 on 2026-10-19: 352 requests, none invalid, none truncated, none retried; plans 330 to 474 words;
  largest prompt 14,243 tokens against a 15,488 limit). See the work log.
* **Presence-rules lock: `draft`** (rules version 0.2).
