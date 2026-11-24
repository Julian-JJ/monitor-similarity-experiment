# Registries

Code: [`monitor_experiment/registry.py`](../../monitor_experiment/registry.py). Files: `configs/monitors.toml`,
`configs/rollout_sets.toml`. Tests: `tests/test_registry_spec.py`.

Both files are read strictly: a missing required key, an unknown key, a bad value or a missing file raises `RegistryError` naming the file
and entry. (This caught a real mistake while building them: a TOML header `[monitors.qwen3-1.7b]` is read as nested tables because of the
dot, so that name is written `[monitors."qwen3-1.7b"]`.)

## `configs/monitors.toml`

Top level: `reference_tokenizer`, the `tokenizer.json` used to **count tokens for chunking, for every monitor**. One tokenizer for all of
them means every monitor sees identical observation chunks and only the model differs. The server reports each call's real prompt
size (`prompt_tokens`), which the runner records and `costs` summarizes (`max_prompt_tokens`) so an overshoot by a monitor with a less
efficient tokenizer is visible. The input limit leaves 512 tokens of margin, and a full 12,000-token chunk plus its prompt (up to about 1,350 tokens) and a plan (up to about 1,000) stays under it, with about 1,100 tokens to spare.

One `[monitors.NAME]` table per model:

| Key | Meaning |
| --- | --- |
| `model_id`, `revision` | Hugging Face id and pinned revision (`UNPINNED` until downloaded; `scripts/download_monitor.py` prints the revision to pin, and `monitor_download.verify` checks a model directory against the pin. Qwen3-14B and Qwen3-32B are pinned). A `model_id` starting `TBD` is a placeholder |
| `family`, `size_b`, `active_b`, `architecture` | for the similarity relation; architecture is `dense` or `moe`; `active_b` optional |
| `provider`, `open_weights` | recorded; every run model is served on the cluster |
| `base_url` | where it is served (can be overridden with `--base-url`) |
| `context_tokens`, `output_reserve` | the monitor's window, and tokens kept for its reply |
| `sampling` | `temperature`, `top_p`, `max_tokens` (must not exceed `output_reserve`) |
| `thinking` | whether the model thinks by default |
| `reasoning_parser` | optional vLLM `--reasoning-parser` name; `qwen3` for the Qwen3 family, unset for GPT-OSS and Gemma because the right name was not verified. Part of the monitor's identity |
| `reasoning_control` | optional, e.g. `kind = "reasoning_effort"`, `default = "medium"` for GPT-OSS |
| `verified` | false until the model has been downloaded and its identity checked |
| `notes` | free text (not part of the monitor's identity) |

`Monitor.identity()` is everything except `base_url`, `notes` and `verified`, so moving a server does not change results' identity but
changing the model, revision, sampling or context does.

### Relation to the fixed agent

`Monitor.relation_to(actor)` returns one of `same_model`, `same_family_smaller`, `same_family_larger`, `same_family_other_architecture`,
`different_family`. This is the similarity descriptor the pre-registered contrasts use. Current entries:

| Monitor | Relation | Status |
| --- | --- | --- |
| `qwen3-14b` | same_model | installed, revision pinned |
| `qwen3-1.7b`, `qwen3-4b` | same_family_smaller | not downloaded |
| `qwen3-32b` | same_family_larger | not downloaded |
| `qwen3-30b-a3b` | same_family_other_architecture | **unverified**: listed from memory of the Qwen3 family |
| `gpt-oss-120b` | different_family | not downloaded; memory use under its quantization unchecked |
| `gemma-large` | different_family | **placeholder** (`TBD-gemma`); cannot run until a model is chosen |

`Monitor.runnable()` raises for placeholders; the runner and the client call it.

## `configs/rollout_sets.toml`

`[actor]` is the fixed agent (model, revision, family, size, architecture); it is recorded in every run manifest and is the reference for
the relation above. `[objectives]` names the objective table. `[sets.NAME]` entries have `root` (relative to the repository), `manifest`,
`status` (`available` or `planned`) and `description`. `Registry.load_set(name)` loads and verifies a set, with a specific error for a
planned set that does not exist yet.

## Adding a monitor

1. Download the model and pin its revision. 2. Add a `[monitors.NAME]` table with `verified = true` once its identity is checked.
3. Serve it (one model per server) and put the address in `base_url` or pass `--base-url`. 4. List the name in an experiment file.
The first run's manifest records what the server reported it was serving, and the CLI warns if that does not look like `model_id`.
