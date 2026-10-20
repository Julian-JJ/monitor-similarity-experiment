# Building a collection from a rollout cache

Code: [`monitor_experiment/collection_builder.py`](../../monitor_experiment/collection_builder.py); entry point `scripts/build_collection.py`.
Tests: `tests/test_collection_builder.py` (6), which use the **real** rollout generator with a scripted client, so the cache layout under test is the real one.

`scripts/generate_rollouts.py` writes a *cache* (`rollouts/<task>/<variant>/<id>.json`, `followups/<rollout id>/<id>.json`, `entries/<rollout id>.json`). The
cached batch in `rollouts_original_clean/` is a cleaned *collection* built from such caches by a script that is not in this repository. `build_collection`
does the same job in the same layout, so newly generated rollouts (the `main_only` controls) load with `RolloutSet` like the originals
([data-layer](data-layer.md)).

```bash
python scripts/build_collection.py --cache $ME/cache --out rollouts_main_only_clean --name main_only_v1 \
    --expect 12 --source-job $JOBID --hardware "H200 x1" --config $ME/configs/rollouts-main-only.toml
```

## What it does

1. For every `entries/*.json` of the variant, keep the sample only if its actor is `complete` and it has exactly one follow-up that is `complete`.
   **Nothing about the rollout's outcome decides this**: a control that happened to achieve an objective is kept like any other.
2. Samples that are not kept are listed in the manifest's `excluded` with the reason: `never started`, `actor error: <type>: <message>`, `actor running`, `follow-up not complete`.
   With `--expect N` the samples 0 to N−1 of every task are expected, so missing ones are listed.
3. Copy the two files byte for byte to `<task>/<variant>/sample_NN/{rollout,followup}.json` and check each copy's SHA-256 against its source.
4. Refuse to proceed if the kept rollouts disagree on generation settings, implementation hash or model revision (they must come from one configuration).
5. Write `manifest.json`: the pairs (ids, checksums, turns, termination, labels, served model name, paths), `excluded`, `counts` (requested, kept, excluded, by task), the
   generation settings, model revision, `runtime_implementation_hash`, the config file's SHA-256, the builder's SHA-256, the selection rule and limitations.

It refuses to write into a directory that already has a manifest and fails if no complete pair exists. The result is verified by `RolloutSet.from_manifest` like any
collection. To use it, set `status = "available"` for `main_only_v1` in `configs/rollout_sets.toml` once `rollouts_main_only_clean/` exists.


## First use on real output (2026-10-20)

`main_only_v1` was built from job 30068222's cache: 34 pairs kept, 2 excluded for execution errors (`Unparsed tool call: start vLLM with --tool-call-parser hermes`), by task 12 / 11 / 11. Execution status alone decided retention. The builder, the checksum-verified load and the duplicate guard all worked on real output. See the [work log](../worklog.md) section T.
