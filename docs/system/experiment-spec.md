# Experiment files

Code: [`monitor_experiment/spec.py`](../../monitor_experiment/spec.py). Examples: `configs/experiments/`. Tests: `tests/test_registry_spec.py`.

An experiment file is TOML. Unknown keys, unknown axes, unknown options, duplicate values and unimplemented values are errors.

```toml
name        = "baseline"                    # the run directory is runs/<name>/
monitor     = "qwen3-32b"                   # or: monitors = ["qwen3-14b", "qwen3-4b", ...] (a grid axis)
rollout_sets = ["original_clean"]           # add "main_only_v1" once the controls exist
told        = ["malicious", "benign"]       # optional; default both
[grid]                                      # every axis takes a list; the runner runs the cross product
scope       = ["action", "cot", "all"]      # required
task_context = ["none", "plan"]             # optional axes below
[options]
samples = 4
```

## Axes (`[grid]`)

| Axis | Values now | Default | Named in the plan, not implemented |
| --- | --- | --- | --- |
| `scope` | `action`, `cot`, `all` | none: required | |
| `task_context` | `none`, `plan` | `none` | `execute`, `plan_compare` |
| `hierarchy` | `upstream-limits` (32,768 context, 16,768 reply reserve, 12,000-token chunks), `long-context` (131,072 / 16,768 / 100,000) | `upstream-limits` | |
| `partial_cot` | `off`, `turns:<p>`, `tokens:<p>` with 0 < p ≤ 1 | `off` | |
| `followup_visibility` | `none` | `none` | `answer`, `cot`, `all` |
| `prompt` | `upstream_ad` | `upstream_ad` | `structured` |
| `reasoning` | `default`, `off` (thinking disabled), `low`, `medium`, `high` (reasoning effort; needs a monitor with `reasoning_control.kind = "reasoning_effort"`) | `default` | |

`monitor` / `monitors` is the remaining axis. `told` is not an axis of the cell: every rollout is judged under each told objective
within the same cell and the results are pooled or split at scoring time.

Validation of a cell against its monitor: the hierarchy preset must fit the monitor's registered context; the monitor's reply limit must
fit the preset's reserve; an effort level needs an effort-controllable monitor; `reasoning = "off"` needs a thinking monitor; and
the hierarchy parameters must pass `hierarchy.check_params`.

## Options (`[options]`)

| Option | Default | Part of a cell's identity? | Meaning |
| --- | --- | --- | --- |
| `samples` | 4 | no | independent monitor samples per rollout and told objective (upstream: 4) |
| `seed` | 0 | yes | base for all seeds |
| `bin_size` | 6 | yes | analyses combined per call (pre-registered value; the library default is 4) |
| `chunk_tokens` | preset's | yes | overrides the preset's chunk size |
| `margin_tokens` | 512 | yes | slack under the input limit |
| `truncate_chars` | 2000 | yes | tool-result cut (upstream's rule); counted and recorded |
| `labels` | true | yes | turn labels in the rendered transcript |
| `max_attempts` | 2 | yes | tries per node before it is invalid |
| `single_pass_if_fits` | true | yes | one unmodified-prompt call when the whole transcript fits |
| `prep_samples` | 3 | yes | independent plans per task for `task_context = "plan"` |
| `concurrency` | 8 | no | simultaneous requests |
| `keep_monitor_reasoning` | false | no | store the monitor's reasoning text (large) instead of its length |
| `item_limit` | 0 | no | only the first N rollouts of each (origin, variant, task) group; 0 = all (the pilot uses 1) |

Options marked "no" change how many units run or how fast, never what one unit's result is, so changing `samples` adds units to an
existing run without invalidating the ones already done.

## Cells and cell IDs

`expand(spec, registry, fingerprints)` returns one `Cell` per combination of monitor and axes. Its `cell_id` is the SHA-256 of: the
monitor's identity; the axis values; the resolved hierarchy parameters; the identity options above; and the **fingerprints** (hashes of the
five prompt files, tool lists, objective table and the reference tokenizer; the councils, comparisons and presence rules are deliberately not part of it, see [freeze](freeze.md)). Editing any prompt
file therefore changes every cell ID, and nothing computed under the old prompt can be mistaken for a result under the new one. Two
cells with identical settings are an error.

## Overrides

`--set path=value` (TOML syntax; repeatable) changes a parsed spec without editing the file, for example
`--set grid.scope=cot --set options.samples=2 --set grid.hierarchy='"long-context"'`. A scalar under `grid.` becomes a one-item list.
`--monitor NAME` selects one monitor from the list (needed because one server serves one model).

## Run directories accumulate

The run directory is `runs/<name>/` (not hashed), and units are keyed by cell. Rerunning with a larger `samples`, with another monitor,
or with another rollout set (once controls exist) adds units to the same directory; the manifest keeps every cell and session seen. If
you change anything that is part of a cell's identity, you get new cells in the same directory and the old ones remain, scored
separately. To start clean, use a new `name`.

## Pre-registered files

| File | Purpose |
| --- | --- |
| `pilot-format-only.toml` | the format-only pilot: Qwen3-14B, scopes action and cot, both contexts, one rollout per task and variant, one sample |
| `baseline.toml` | MonitorBench's own monitor (Qwen3-32B), no context, three scopes, cached rollouts |
| `preregistered-grid.toml` | the grid behind P1 to P4; needs the control rollouts, so it refuses to run until `main_only_v1` exists |
