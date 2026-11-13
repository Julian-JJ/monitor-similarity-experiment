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
| `family`, `size_b`, `active_b`, `architecture` | for the similarity relation; architecture is `dense` or `moe`; `active_b` optional. Gemma 4 uses Google's published total counts in `size_b`; E2B/E4B effective counts are recorded in notes, not mislabeled as MoE active counts |
| `provider`, `open_weights` | recorded; every run model is served on the cluster |
| `base_url` | where it is served (can be overridden with `--base-url`) |
| `context_tokens`, `output_reserve` | the monitor's window, and tokens kept for its reply |
| `sampling` | `temperature`, `top_p`, `max_tokens` (must not exceed `output_reserve`) |
| `thinking` | whether the model thinks by default |
| `reasoning_parser` | optional vLLM `--reasoning-parser` name; `qwen3` for Qwen3 and `gemma4` for the concrete Gemma 4 entries, unset for GPT-OSS and the legacy Gemma placeholder. Part of the monitor's identity |
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
| `qwen3-32b` | same_family_larger | revision pinned; registry records a download, serving unverified |
| `qwen3-30b-a3b` | same_family_other_architecture | **unverified**: listed from memory of the Qwen3 family |
| `gpt-oss-120b` | different_family | not downloaded; memory use under its quantization unchecked |
| `gemma-large` | different_family | **placeholder** (`TBD-gemma`); cannot run until a model is chosen |
| `gemma4-e2b` | different_family | `google/gemma-4-E2B-it`; not downloaded or cluster-tested |
| `gemma4-e4b` | different_family | `google/gemma-4-E4B-it`; not downloaded or cluster-tested |
| `gemma4-12b` | different_family | `google/gemma-4-12B-it`; not downloaded or cluster-tested |
| `gemma4-31b` | different_family | `google/gemma-4-31B-it`; not downloaded or cluster-tested |

The proposed Qwen pool uses Qwen3-1.7B, 4B, 14B, and 32B. The initial "1.4B"
request was interpreted as Qwen3-1.7B in the original plan; its registry name
remains `qwen3-1.7b`. [Official Qwen3-1.7B model card](https://huggingface.co/Qwen/Qwen3-1.7B)

The four concrete Gemma 4 entries were added on 2026-11-13. Their identifiers,
dense architecture, and parameter counts come from Google's model cards:
[E2B](https://huggingface.co/google/gemma-4-E2B-it),
[E4B](https://huggingface.co/google/gemma-4-E4B-it),
[12B](https://huggingface.co/google/gemma-4-12B-it), and
[31B](https://huggingface.co/google/gemma-4-31B-it).
E2B/E4B have 5.1B/8B total parameters including embeddings and 2.3B/4.5B effective
parameters. The 12B/31B entries record 11.95B/30.7B total parameters. The
`gemma4` reasoning parser follows the [official vLLM recipe](https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html).

These additions use the existing pool's 32,768-token serving window, 16,768-token
output reserve, temperature 0.6 and top-p 0.9. These are experiment defaults,
not native context limits or a claim to reproduce Google's recommended sampling.
New revisions are `UNPINNED` and `verified = false` until download and cluster
validation. Choose the new names explicitly in experiment files. The existing
`gemma-large` placeholder and frozen comparisons/councils are retained; adding
these entries does not silently choose a model for those earlier comparisons.

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
