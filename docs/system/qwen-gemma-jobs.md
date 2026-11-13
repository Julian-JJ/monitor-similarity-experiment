# Submit the remaining Qwen/Gemma baselines

Entry point: [`submit_qwen_gemma_baselines.sh`](../../junlin/submit_qwen_gemma_baselines.sh).
Experiment: [`qwen-gemma-baseline.toml`](../../configs/experiments/qwen-gemma-baseline.toml).

The default models are Qwen3-1.7B, Qwen3-4B, and Gemma 4 E2B/E4B/12B/31B,
using their registry names. Qwen3-14B and Qwen3-32B already have completed baseline
cells and are excluded. Qwen3-30B-A3B can be selected explicitly.

## Match to the completed baseline

The specification uses the same `original_clean` and `main_only_v1` collections,
both told objectives, all three observation scopes, four monitor samples,
thinking enabled, no plan, and no follow-up observations. It uses the frozen
prompts, 32,768 context, 16,768 output reserve, 12,000-token chunks, bins of six,
temperature 0.6 and top-p 0.9. With the existing 75 transcripts, that is 1,800
monitor units per model. Request concurrency is 32, as in the completed run.

Results append to `$ME/runs/baseline`. The existing 14B/32B cells remain in the
manifest; completed units are reused. No actor trajectories are generated here.

## Run on the cluster

Sync this branch to the cluster before submitting. The analysis environment must
have the normal project dependencies, `tokenizers`, and `huggingface_hub` (see
`requirements.txt`, `requirements-analysis.txt`, and `requirements-download.txt`).
The two rollout collections and pinned reference tokenizer must be available
where the registries expect them. The submitter checks those paths and the
prompt freeze before creating jobs.

Select a serving environment that supports the selected Gemma 4 checkpoints,
including the unified 12B model, and `--reasoning-parser gemma4`. The existing
Qwen environment may be too old. `GEMMA_SERVING_PY` is the path to that
environment's Python executable (its `bin/python`), not a model directory or a
vLLM script. It is optional: when unset, Gemma jobs use `SERVING_PY` too. If one
environment supports both model families, use the same interpreter for both.
Setting either variable only chooses an existing interpreter; it does not create
an environment or install packages. The path below is an example, not an
environment created or verified by this project. This workflow has been tested
offline, not on Slurm or with Gemma inference.

```bash
export ME=/nfs/roberts/project/cpsc4880/cpsc4880_as4833
export FRAMEWORK="$ME/monitor-framework"
export GEMMA_SERVING_PY="$ME/envs/monitor-vllm-gemma4/bin/python"  # an existing, compatible environment

# Print all job commands without Slurm, downloads, or writes:
bash "$FRAMEWORK/junlin/submit_qwen_gemma_baselines.sh" --dry-run

# Submit the default six models:
bash "$FRAMEWORK/junlin/submit_qwen_gemma_baselines.sh"

# Or submit a subset / the optional MoE model:
bash "$FRAMEWORK/junlin/submit_qwen_gemma_baselines.sh" qwen3-4b gemma4-e4b
bash "$FRAMEWORK/junlin/submit_qwen_gemma_baselines.sh" qwen3-30b-a3b
```

`ME`, `FRAMEWORK`, `MODELS_DIR`, `ANALYSIS_PY`, `SERVING_PY`, and
`GEMMA_SERVING_PY` can be overridden. `FRAMEWORK` defaults to the checkout
containing the script. CPU preparation defaults to partition `day`, 4 CPUs,
16 GB RAM and four hours. GPU jobs default to `gpu_h200`, one H200, 8 CPUs,
96 GB RAM and eight hours. `ACCOUNT`, `CPU_PARTITION`, `GPU_PARTITION`,
`CPU_TIME`, `GPU_TIME`, `GPU_COUNT` and `GPU_MEM` override resources; the GPU
type stays H200. `GPU_COUNT` also sets tensor parallelism and GPU-hour accounting.

## Preparation, dependencies, and provenance

Each model gets two Slurm jobs:

1. A CPU preparation job downloads missing weights, or verifies/reuses an
   existing complete download. It resolves the model to an immutable revision
   and writes a private registry under the submission's log directory. The source
   registry is not modified. An existing mismatched or damaged download fails
   verification instead of being silently replaced.
2. A GPU job depends on successful preparation. Both serving and inference use
   that private registry, so the recorded model identity contains the actual
   commit instead of `UNPINNED`. Verification does not mark the model's inference
   behavior as validated; `verified` retains its source value.

GPU jobs are chained sequentially with `afterany` to keep one writer to the shared
run directory; CPU preparation jobs can overlap. A failed monitor job allows the
next model to run. Failed preparation cancels that model's GPU job, allowing the
chain to advance. An additional file lock rejects
concurrent writers even when jobs were submitted outside this wrapper. If a
baseline job is already queued or running, set `DEPENDENCY_JOB_ID` to its ID.

Job IDs and dependencies are appended immediately to
`$ME/logs/qwen-gemma-<timestamp>-<pid>/submissions.tsv`, including preparation
jobs if a later submission fails. Each registry directory also contains
`resolved-model.json` with the verified download manifest and registry hash.
GPU jobs write serving manifests, status/server logs, metrics, and per-monitor
label-free summaries using the existing job script. Re-running the submitter
reuses complete downloads and completed monitor units. Keep the shared checkout
and frozen experiment inputs stable while these jobs are queued or running.
