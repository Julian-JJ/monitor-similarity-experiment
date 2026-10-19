# Fingerprints and the freeze

Code: [`monitor_experiment/freeze.py`](../../monitor_experiment/freeze.py); entry point `scripts/freeze.py`; lock file `prompts/prompts.lock.json`.
Tests: `tests/test_freeze.py`. Why: [07 section 2.8](../plan/07-design-decisions.md#28-prompts).

## Two layers

**Fingerprints (always on).** `fingerprints()` hashes the files that shape a result: the prompts (`monitor_chunk_notice.txt`, `monitor_reduce.txt`,
`monitor_plan.txt`, `monitor_plan_section.txt`), MonitorBench's vendored monitor prompt, `configs/councils.toml`, `configs/presence_rules.json`,
`configs/comparisons.toml`, plus the tool lists, the objective table and the reference tokenizer. They enter every **cell ID**, so editing any of them
changes every affected cell and old results cannot be mistaken for new ones.

**The lock (an agreement).** `prompts/prompts.lock.json` records those hashes with a status:

| Status | Meaning | Effect |
| --- | --- | --- |
| missing | no lock file | the runner warns in the manifest only |
| `draft` | wording may still change | a mismatch is reported, not fatal; the manifest records `prompts_status: draft` and every report warns |
| `frozen` | wording is fixed for confirmatory runs | a mismatch **stops the runner** with the list of changed files |

## Workflow

1. Write prompts. `python scripts/freeze.py write --status draft` records them (the current state).
2. Run the format-only pilot (`configs/experiments/pilot-format-only.toml`). The pilot reports validity, length and finish reasons; it should not be used
   to tune wording to detection performance. Wording changes to fix format problems are logged.
3. `python scripts/freeze.py write --status frozen`, then commit the lock. From then on any change is an **amendment**
   ([07 amendment log](../plan/07-design-decisions.md#amendment-log)): a dated entry with the reason and whether results had been seen.
4. `python scripts/freeze.py status` shows the status and any file that differs (exit status 1 if frozen and violated, or missing).

Current state: **`draft`**. The prompts have not been piloted on a model, so they are not frozen.
