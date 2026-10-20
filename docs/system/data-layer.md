# Data layer

Code: [`monitor_experiment/data.py`](../../monitor_experiment/data.py). Tests: `tests/test_data.py`.

## Collections

A **collection** is a directory with a `manifest.json` listing complete actor rollouts and the checksums of their files. The
cached batch (`rollouts_original_clean/`, 41 pairs) is one; the planned control rollouts will be another in the same layout.

```text
rollouts_original_clean/
  manifest.json
  <task>/<variant>/sample_NN/rollout.json     the actor's messages, reasoning, tool calls, evaluation, final state
  <task>/<variant>/sample_NN/followup.json    the one cached generic follow-up
```

`RolloutSet.from_manifest(name, root)` reads the manifest and **verifies**, for every pair, that both files exist, that their SHA-256
equals `actor_sha256` / `followup_sha256`, that the rollout's `status` is `complete` and its `rollout_id` equals the manifest's, that
the variant is known, and that no rollout is listed twice. All problems are reported together. `verify=False` skips the checks
and marks the set `verified=False` (recorded in run manifests); it exists for tests and for scoring very large runs, not for results.

Manifest fields used: `task`, `variant` (`malicious`, `benign` or `main_only`), `sample`, `rollout_id`, `actor` and `followup`
(paths relative to the collection), `actor_sha256`, `followup_sha256`, and optionally `source_job_id`, `hardware`, `termination`, `turns`.

## Items, and what a monitor may see

An `Item` is one rollout. Its `item_id` is `task/variant/sample_NN`. Two accessors keep observable data and labels apart:

| Accessor | Returns | Contains |
| --- | --- | --- |
| `item.observation()` | `Observation` | task name, the **main-task text**, and the user, assistant and tool messages. **No system message.** |
| `item.labels()` | `Labels` | `malicious`, `benign` (did the agent achieve each side objective) and `main_success` |

The system prompt is excluded because it holds the hidden objective and the agent's instructions. The hidden objective is given to the
monitor deliberately, through the objective table below. `item.group` is `origin/variant/task` (for example
`cached/malicious/bank_transfer_2`): the stratum within which the bootstrap resamples rollouts. `item.origin` is `control` for `main_only`
rollouts and `cached` otherwise.

## The objective table

`configs/objectives.json` holds one text per (task, objective): six entries, each with a SHA-256 and the number of rollouts it was seen
in. It is built by `scripts/build_objective_table.py` from a collection's system messages, and the build **fails** if one
(task, objective) has more than one distinct text across samples (it does not: verified for all six). It matters because:

* control rollouts have no objective in their system message;
* a rollout judged under the *other* objective needs that objective's text.

`ObjectiveTable.from_json` re-checks each text against its checksum. Open item: the texts have not yet been compared with the vendored
task definitions' own `secondary_task` / `secondary_task_benign` (that needs the environment's heavy dependencies; see
[the decisions document](../plan/07-design-decisions.md#4-open-items)).

## Pairs and roles

A **pair** is an item judged under one told objective. `make_pairs(items)` gives every item both objectives. A pair's label is the item's
recorded outcome for the objective told, and its **role** says what kind of evidence it is (`pair_role`):

| Role | Meaning | In the 41 cached rollouts |
| --- | --- | --- |
| `positive` | the agent achieved the told objective (any variant) | 21 malicious-told, 18 benign-told |
| `clean_negative` | a control rollout (no hidden objective) that did not achieve it | none yet |
| `cross_negative` | the agent was told to pursue the *other* objective | 20 malicious-told, 20 benign-told |
| `own_failure` | the agent was told to pursue this objective and missed it | 0 malicious-told, 3 benign-told |

One malicious `bank_transfer_2` rollout achieved both objectives and is positive under both. The roles are the strata the metrics use
([metrics](metrics.md)); why cross-objective negatives are only secondary is explained in
[the decisions document](../plan/07-design-decisions.md#29-evaluation-design-positives-clean-negatives-cross-objective-negatives).

## Adding the control rollouts

The controls have a `manifest.json` in this format, built by `scripts/build_collection.py` ([collections](collections.md)). The `main_only_v1` entry in `configs/rollout_sets.toml` is `available`
(34 pairs; checksum-verified on load). A set whose entry is `planned` fails to load with a message saying so, and `--dry-run` skips it.
