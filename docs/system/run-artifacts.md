# Run artifacts

A run directory `runs/<name>/` holds the following. Everything is JSON or JSONL except `metrics.csv` and `report.md`. Written by
[`runner.py`](../../monitor_experiment/runner.py), `compare.py` and `report.py`.

| File | Written by | Contents |
| --- | --- | --- |
| `manifest.json` | run | everything needed to reproduce and audit the run |
| `items.jsonl` | run | one line per finished unit: the verdict and its cost |
| `nodes.jsonl` | run | every monitor call's text and bookkeeping, per unit |
| `plans/<monitor>.jsonl` | run | the monitor's reference plans |
| `errors.json` | run | units that failed with a transport error (only if any) |
| `metrics.json`, `metrics.csv` | score | results with intervals; the CSV is one tidy table |
| `comparisons.json` | compare | the pre-registered comparisons |
| `report.md` | report | the readable summary |

## `manifest.json`

`schema_version`, `name`, `spec` (the parsed experiment file) and `spec_path`; `cells` (each `cell_id`, `label`, `params`, `options`,
`partial_cot`, `relation_to_actor`); `monitors` (each monitor's identity); `served` (what each server reported it was serving, keyed
`monitor|reasoning`); `actor` (the fixed agent); `rollout_sets` (status, manifest SHA-256, rollouts used and available, verified);
`told`; `samples`; `item_ids` (the rollouts the run used, accumulated across invocations); `fingerprints` (hashes of prompts, tool lists, objectives, councils, rules and the tokenizer); `prompts_status` and
`prompts_problems`; `git` (commit, branch, whether the tree was dirty, and `source`: `git`, or `sync file` on the cluster copy, which has no `.git` and reads `.sync-commit.json` written by `mihai/cluster/sync_to_cluster.sh`, or `none` with commit and dirty unknown); Python and platform; `compute` (GPU type, count, job id);
`started_at`, `finished_at`; and `sessions` (one entry per invocation: times, wall seconds, units run, errors).

## `items.jsonl` (one verdict per unit)

| Field | Meaning |
| --- | --- |
| `unit_id`, `cell_id`, `item_id`, `told`, `sample`, `seed` | identity of the unit |
| `status` | `complete`, `invalid` (a node had no valid answer), or `error` (the tree could not be run within the budgets) |
| `letter`, `detected` | the root's A–D letter; `detected` is true iff `A`, and `null` unless `status` is `complete` |
| `hierarchical`, `chunks`, `levels` | whether the transcript was chunked, into how many chunks and levels |
| `calls`, `model_requests` | tree nodes executed; requests including retries |
| `prompt_tokens`, `completion_tokens`, `max_prompt_tokens` | as the server counted them; the largest single prompt |
| `latency_seconds`, `critical_path_seconds`, `call_latencies` | summed request latency; per-level-slowest sum; each request |
| `plan_id` | the reference plan used, or `null` |
| `partial_cot` | what fraction of the reasoning was shown, or `null` |
| `truncated_tool_results` | tool results cut at the character limit |
| `error` | present when `status` is `error` |
| `finished_at` | timestamp |

## `nodes.jsonl`

One line per tree node: `unit_id`, `node_id`, `level`, `kind` (`chunk` or `reduce`), `children`, `first_turn`, `last_turn`, `prompt_tokens`,
`prompt_sha256` (the prompt is reconstructible, so it is not stored), `status`, `verdict`, `text` (the node's final analysis), and `attempts`,
each with its `seed`, `valid`, `reason` if invalid, `verdict`, `finish_reason`, `text`, `usage`, `latency_seconds`, and the monitor's reasoning as
`reasoning_chars` (its length) or `reasoning` (the text, with `keep_monitor_reasoning`). Reasoning text is dropped by default because it can be
tens of thousands of tokens per call. Nodes whose unit has no line in `items.jsonl` are orphans from an interrupted run.

## `plans/<monitor>.jsonl`

`plan_id`, `task`, `index`, `text`, `tokens`, `prompt_sha256`, the attempts (validity, finish reason, usage, latency; no reasoning), `created_at`.

## `metrics.json`

`run`, `told`, `samples`, `prompts_status`, `git`, `rollout_sets`, `bootstrap` (replicates, seed, level), and `cells`, each with `cell_id`, `label`,
`relation_to_actor`, `units_expected`, `units_found`, `complete`, `results` and `cost`. `results` has `pooled`, `malicious` and `benign`, each with
`counts` (pairs, requested, valid, detected, decided, decided_detected per role) and `metrics` (each `value`, `reason` when undefined, and `low`,
`high`, `defined` for the interval). Definitions: [metrics](metrics.md). Also `compute_by_monitor` (per monitor: wall seconds, GPU-hours, GPU type, job ids, units run; a session that ran several monitors or none is listed
under `unattributed_sessions` instead of being split) and `sessions` (job id and the commit each session ran from, or `not recorded` for sessions made before this was added). A cell's `cost` has no GPU-hours: a job is shared by the cells it runs ([costs](costs.md)).

In `manifest.json`, `git` is the **latest invocation's** commit and each entry of `sessions` now carries its own `git`; runs made earlier have it only at manifest level, so for a run built over several invocations the earlier commits must come from the work log.

## `metrics.csv`

Columns: `cell_id`, `monitor`, `scope`, `task_context`, `hierarchy`, `partial_cot`, `followup_visibility`, `prompt`, `reasoning`,
`relation_to_actor`, `told`, `metric`, `value`, `ci_low`, `ci_high`, `replicates`, `note`. One row per cell × told group × metric; empty value
with a reason in `note` means undefined. Any later plot or analysis can read this one file.

## `comparisons.json`

`metric`, `told`, `bootstrap`, `holm_family`, and `results`: each comparison with `id`, `family` (the scope), `setting`, the two cells' labels,
`primary` and `recall` (each a paired difference with `a`, `b`, `difference`, `low`, `high`, `p_value`, `defined`), `outcome`, `p_holm` and an
optional `note`; skipped comparisons carry a `skipped` reason instead. See [comparisons](comparisons.md).
