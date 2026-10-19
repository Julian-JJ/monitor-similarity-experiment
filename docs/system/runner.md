# The runner

Code: [`monitor_experiment/runner.py`](../../monitor_experiment/runner.py). Entry point: `scripts/run_experiment.py`
([cli](cli.md)). Tests: `tests/test_runner.py` (24, end to end with fake monitors).

## `run_experiment(spec, registry, out_root, make_complete=..., count=..., prompts=..., root=...)`

1. **Freeze check.** `freeze.require_ready`: a `frozen` lock whose files changed stops the run. A `draft` or missing lock only records
   `prompts_status` in the manifest.
2. **Context.** Fingerprints → cells (`spec.expand`) → rollout sets loaded and **verified** → the objective table. `item_limit` is applied here.
   Placeholder monitors fail (`Monitor.runnable`). A planned rollout set with no manifest fails with a message.
3. **Monitor connections.** `make_complete(monitor, reasoning)` returns `(complete, provenance)` for each distinct (monitor, reasoning). The
   command-line tool builds a `MonitorClient`, calls `check()`, and records the served model in the manifest.
4. **Plans.** For every monitor with a `plan` cell, a `PlanBook` writes any missing plans ([plan-context](plan-context.md)). The main-task
   text must be identical across a task's rollouts; otherwise a shared plan is invalid and the run stops.
5. **Manifest.** Written before any unit runs, and merged with an earlier manifest in the same directory (cells, monitors, served models,
   rollout sets and sessions accumulate).
6. **Units.** Every (cell, rollout, told, sample) not already in `items.jsonl` is run on a thread pool of `concurrency` workers. For each unit:
   prepare (cached per cell, rollout and told, so the samples share one plan), seed, run the tree, build the record, append the nodes then the
   record. A unit whose work raises (a transport error that survived the client's retries, or a bug) is **not written**, is listed in
   `errors.json`, and does not stop the others. After all units, if any failed, `RunIncomplete` is raised (exit status 2 in the CLI).
7. **Session.** Wall time, units run and errors are appended to the manifest's `sessions`.

## Resume

`items.jsonl` is the index of finished units. A unit counts as finished whatever its status (`complete`, `invalid` or `error`): those outcomes are
deterministic given the seed and are not retried. A rerun with the same arguments therefore does nothing; after an interruption it runs exactly the
missing units. Nodes are written before the unit's record, so a crash between them leaves **orphan nodes** that the rerun duplicates: always
read `nodes.jsonl` through `items.jsonl` (the unit ids that have a record).

## Seeds

`unit_seed = seed × 10⁹ + (crc32(item_id|told) mod 10⁵) × 10⁴ + sample × 10³`; the tree adds `10 × node ordinal + attempt` (a few hundred at
most), so no two requests in a run share a seed (tested). The base `seed` is part of the cell ID.

## Concurrency

Units run in parallel; the order of completion is not the order of the file. Results do not depend on `concurrency` (tested: records, seeds and call
counts are identical at 1 and 4). One run drives one server per monitor; vLLM batches the concurrent requests.

## Dry run

`dry_run(spec, registry, count=..., prompts=..., root=...)` builds every unit's exact level-0 prompts (identical to a real run's) and prices the
experiment: units, model calls (`estimate_tree`), input tokens (exact for level 0, **estimated** for combining levels at a stated
`--report-tokens`, default 1,000), plan calls, `hierarchical_units`, the largest prompt, and cut tool results. It needs no server, tolerates planned rollout sets
(reporting them `missing`), and caches planning across monitors that share settings. It does **not** know output length or wall time. Its call count
equals a real run's exactly when no combining level is split by the token limit (tested). On the 41 cached rollouts, `baseline.toml` prices at
8,336 calls and about 79.9 M input tokens, identical to the earlier independent calculation.

## `score_run(run_dir, registry)`

Reloads the rollout sets named in the manifest (verified unless disabled), keeps only the rollouts the run used (`item_ids`, so a pilot with `item_limit` is scored against the rollouts it ran), builds the pairs, and for each cell collects its records into per-pair
outcomes, computes the point estimates ([metrics](metrics.md)), the bootstrap intervals and the cost summary ([costs](costs.md)), and writes
`metrics.json` and `metrics.csv` ([run-artifacts](run-artifacts.md)). `complete` is true only if the cell has every expected unit. Partial runs can be
scored; the report says which cells are incomplete.

## Limits

* No streaming and no mid-tree checkpoint: a unit interrupted mid-tree reruns from its first chunk.
* All records are read into memory at scoring time (fine for the sizes here; about 10⁵ lines).
* Transport retries are in the client; there is no run-level retry policy beyond resume.
* The runner never reads a label. Only `score_run` does.
