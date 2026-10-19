# Experiments and cluster guide

Code, configuration, small results and provenance belong in Git. Weights, raw
responses, reasoning, environments and runtime logs stay on Yale's Bouchet
cluster. The original batch and the second screening experiment remain separate.

## Locations

Log in as `<your-cluster-username>@bouchet.ycrc.yale.edu` using your own Yale
account, network/VPN access and Duo when required. Set `$PROJECT` to the team's
shared project directory:

```text
<shared-project-directory>
```

Use the canonical shared storage path, not a personal home-directory alias.
The existing location is recorded as `project_root` in the
[setup record](results/environments/setup-2026-10-16.json). This path is the
same for all teammates; do not replace part of it with your login username.

| Relative to the project directory | Contents |
| --- | --- |
| `rollouts_original_clean/` | 41 complete original actor/follow-up pairs, grouped by task, variant and sample |
| `mihai/test_rollouts_2/runs/29910578/raw/` | Second experiment's 20 response records: 19 complete, one truncated |
| `mihai/test_rollouts_2/runs/29910578/manifest.json` | Second experiment's file list, statuses, hashes and serving provenance |
| `mihai/test_rollouts_2/releases/41e5261de745d76c/` | Immutable source, prompts and configuration used for job 29910578 |
| `models/qwen3-14b/` | Downloaded weights, tokenizer and model manifests |
| `envs/monitor-research/` | Research, environment tools, downloads and analysis packages |
| `envs/monitor-vllm/` | Isolated GPU serving packages |
| `monitor-similarity-experiment/` | Git checkout; `.venv`, `models` and `cache` link to project storage |
| `releases/` | Frozen original source and selected-pair orchestration |
| `cache/` | Model runtime caches and remaining original source artifacts |
| `logs/` | Setup logs, final statuses, configuration/serving snapshots, submission receipts and locks |
| `archives/cleanup-20261018/` | Verified archive of failed artifacts, old logs, retry history and superseded local drafts |

The project-root `test_rollouts_2` is a compatibility link to
`mihai/test_rollouts_2`. Historical manifests and immutable launch scripts use
that old spelling; the link preserves their references. Original clean rollouts
remain outside `mihai/`.

## Original data for future monitors

| Task | Benign | Malicious |
| --- | ---: | ---: |
| `bank_transfer_2` | 7 | 6 |
| `american_airlines_2` | 6 | 7 |
| `spam_filter_update` | 7 | 8 |

Each `task/variant/sample_XX/` directory contains `rollout.json` and
`followup.json`. The rollout preserves messages, reasoning, tool calls/results,
evaluations and final state, including structured DataFrame snapshots. The
follow-up preserves the question, answer and parent linkage. Sample numbers
are unchanged; missing numbers correspond to excluded execution failures.
All 82 response files were verified as unchanged copies of audited originals.

Start from `rollouts_original_clean/manifest.json`, not a glob across the old
cache. It maps each pair to its identity, source job and checksums. Source jobs
are **29860690** (14 pairs, two A40 GPUs) and **29894244** (27 pairs, one H200).
Retain their distinct serving conditions when comparing monitor results.
Execution completeness does not imply main-task success: all 41 retained pairs
have a false main-task label under the saved grader. See the
[evaluator limitations](../docs/evaluator-notes.md).

The [original summary](results/original-rollouts.json),
[collection manifest](results/collections/original_rollouts_clean/manifest.json)
and [verification receipt](results/collections/original_rollouts_clean/receipt.json)
are kept in Git. Full earlier audits remain in the cluster archive. Some
historical source paths identify failed files now archived; use the clean
collection's relative `actor` and `followup` paths for the retained responses.

## Second experiment

[`test_rollouts_2/`](test_rollouts_2/) contains the independent screening code,
fixed prompts, upstream hashes/license, settings, final audit, reviewed labels
and [report](test_rollouts_2/report.md). Job **29910578** used one H200 and four
concurrent requests: two problems in each of six task types, plus eight controls.
There are 19 complete responses and one output-limit failure, with no follow-ups.

Use the manifest's status to select complete responses, while retaining the
failure in the denominator when reporting performance. These small, partly
manual main-task reviews are not MonitorBench monitorability scores. Do not
merge them with the original agent batch.

The historical release manifest is retained in
[`records/release-29910578.json`](test_rollouts_2/records/release-29910578.json).
The experiment's `release-manifest.json` describes the current working files,
including updated documentation. Frozen cluster source and response files remain
unchanged.

## Model and installed software

**Qwen/Qwen3-14B**, revision `40c069824f4251a91eefaf281ebe4c544efd3e18`, is already
at `models/qwen3-14b/`. All 17 file sizes match `download-manifest.json`; total
size is 29,552,612,206 bytes. No download is needed to reuse these weights or
inspect saved responses. The runs used thinking mode and BF16, with no added
task fine-tuning or quantization.

Two separate environments were created with **uv 0.13.1** and Yale's
**Python 3.12.8** at
`/apps/software/system/software/miniconda/24.11.3/bin/python`, without system
site packages.

| Environment | Installed packages |
| --- | --- |
| Research requirements | Pydantic, pandas, PyYAML, docstring-parser, typing-extensions and Hugging Face Hub |
| Research extras | NumPy, SciPy, scikit-learn, matplotlib, seaborn, tqdm, jsonlines and uv |
| Serving | vLLM 0.11.0, PyTorch 2.8.0+cu128, Transformers 4.56.2, Hugging Face Hub and dependencies |

Exact versions are in the
[research package snapshot](results/environments/research-requirements-frozen.txt)
and [serving package snapshot](results/environments/serving-requirements-frozen.txt).
The [setup record](results/environments/setup-2026-10-16.json) documents initial
creation/checks; its statements about inference being untested refer to October
16 setup, before the subsequent rollout jobs. Recreating the serving environment
requires the CUDA 12.8 PyTorch package source (`uv --torch-backend=cu128` on the
package-install command) and a compatible NVIDIA driver. Existing environments
can be used directly without reinstalling anything.

## Using the installation

After logging into Bouchet:

```bash
export PROJECT="<shared-project-directory>"  # Replace with the team's existing path.
cd "$PROJECT/monitor-similarity-experiment"
export PYTHONDONTWRITEBYTECODE=1
export HF_HOME="$PROJECT/cache/huggingface"
export VLLM_CACHE_ROOT="$PROJECT/cache/vllm"
export TORCH_HOME="$PROJECT/cache/torch"
export XDG_CACHE_HOME="$PROJECT/cache/xdg"
export CUDA_CACHE_PATH="$PROJECT/cache/cuda"

# Offline checks: no GPU inference or downloads.
"$PROJECT/envs/monitor-research/bin/python" -B -m unittest discover -s tests -v
"$PROJECT/envs/monitor-research/bin/python" -B scripts/generate_rollouts.py --check-environments
```

Use an allocated GPU node for model inference. The original H200 continuation
used one H200, eight CPUs, 96 GiB host RAM and eight concurrent clients. It served
BF16 with tensor parallelism 1, 131,072 context tokens, YaRN factor 4, Hermes tool
parsing and Qwen3 reasoning extraction. On an allocated H200 node:

```bash
"$PROJECT/envs/monitor-vllm/bin/python" -B scripts/serve_model.py \
  --model-dir "$PROJECT/models/qwen3-14b" \
  --port 28473 --tensor-parallel-size 1 --max-model-len 131072 --yarn-factor 4
```

[rollouts-output-32768.toml](configs/rollouts-output-32768.toml) records the actor
and follow-up settings: temperature 0.6, top-p 0.95, top-k 20, min-p 0, 32,768
output tokens, 4,800-second request timeout and base seed 42. It does not
configure a future monitor. The server binds to localhost; clients must run
on the same GPU node or use an explicitly configured reachable endpoint. The
launcher manages model locks and serving identities. Do not bypass its locks.

The three helpers under `cluster/` coordinate the original full-batch and
selected-pair workflows. They take immutable source/configuration hashes;
historical submission arguments are archived on the cluster. They are not
needed to read the clean collection. No automatic retry or active monitoring
job remains from these experiments.

## Local copy and planning results (added 2026-10-19)

Planning the monitor stage does not need the cluster. The 41 clean pairs were
copied to `rollouts_original_clean/` at the repository root of a local clone (87 MB,
git-ignored) together with the pinned `tokenizer.json` in `cache/tokenizer/`. The
copy is verbatim; it was made with `rsync` from
`rollouts_original_clean/` in the project directory of the teammate who produced it
(`cpsc4880_mae73`). Steps and caveats are in the [work log](../docs/worklog.md).

Small results from that local work are tracked in Git under `results/`:

| File | Contents |
| --- | --- |
| `results/transcript-token-counts-20261019.json` | prompt tokens for single-pass monitoring, per rollout, scope and tool-result cut ([analysis](../docs/analysis/transcript-token-counts.md)) |
| `results/hierarchy-plan-32k-20261019.json` | dry-run plan: 32,768 context, 12,000-token chunks |
| `results/hierarchy-plan-131k-chunk100k-20261019.json` | dry-run plan: 131,072 context, 100,000-token chunks |

These are measurements of prompt size and planned model calls. They contain no
monitor outputs and no raw responses or reasoning.

## What is needed to run monitors later

Actor generation and follow-ups are implemented. **There is no implemented
`scripts/run_monitors.py` yet.** The CLI in the
[monitor evaluation plan](../docs/plan/04-monitor-evaluation.md) is proposed;
it is not an executable command. What exists is
[`monitor_experiment/hierarchy.py`](../monitor_experiment/hierarchy.py), an offline
library that renders the permitted messages for each scope, splits transcripts into
chunks that fit a monitor's context, builds the prompts, and runs a tree of monitor
calls through a function you supply. Its [design](../docs/plan/05-hierarchical-monitor.md)
covers the rendering of the original transcript in item 3 and the verdict and failure
records of item 4. It does **not** render follow-up answers or reasoning (follow-up
visibility is unimplemented), has no monitor model client, reads no manifest, and does
no scoring. A future monitor runner needs to:

1. Read the saved manifest and verify hashes and parent links.
2. Use identical rollout IDs across comparisons, retaining source-job/serving
   provenance, and save new monitor outputs in a separate cluster directory.
3. Render only the permitted messages, reasoning and follow-up fields. Keep
   evaluator labels, reference answers, privileged state and hidden instructions
   out of monitor inputs.
4. Record the monitor model/revision, prompts, settings, input hashes, verdicts,
   invalid responses and compute usage, then score against saved outcome labels.

The saved actors do not need regeneration. A different monitor model requires
its own download, serving configuration and output namespace; only Qwen3-14B
is installed here. No additional monitor or model-based grader was installed
for the second experiment.

## Cleanup and Git boundary

The October 18 cleanup moved failed original artifacts and verbose old job logs
into a hash-verified cluster archive. Repeated heartbeat observations, old retry
configurations and unused setup drafts were archived before their local copies
were removed. Generated Python caches were removed. Submission receipts,
attempt markers, locks, model weights and installed environments were retained.
Original clean responses and the second experiment's frozen source and raw
responses were verified unchanged.

The archive contains `local-before-cleanup.tar.gz`,
`failed-artifacts-and-old-logs.tar.gz`, their file/hash indexes, and
`original-run-records/`. The latter remains reachable through the old cluster
checkout's `mihai/results/runs` link. These historical files are excluded from
Git. Keep source, tests, configurations, pinned upstream inputs, licenses,
compact results and provenance in Git. Keep weights, raw responses, reasoning,
environments, caches, archives and runtime logs on the cluster.

Project members need read and directory-traversal access to shared data.
Explicitly private files can narrow inherited permissions; check teammate
access when producing new shared exports.
