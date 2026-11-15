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

### Automatic setup and commands after a new login

From the repository root, submit the CPU setup job:

```bash
sbatch junlin/setup.sbatch
```

Setup uses your account's project directory (for Junlin, `cpsc4880_jjj49`) and
the shared data under `cpsc4880_mae73`. It creates/repairs a private analysis
environment and a separate Gemma serving environment, reuses the shared Qwen
serving environment when available, links the existing collections, and restores
the pinned reference tokenizer. **No model weights are downloaded.** The Gemma
installation uses the [official vLLM CUDA 12.9 nightly recipe](https://docs.vllm.ai/projects/recipes/en/stable/Google/Gemma4.html#installing-vllm)
with PyPI explicitly enabled. Re-running `--install` can update serving packages;
use `--check` for verification without installation or writes.

The setup job's output is `slurm-<jobid>.out` in the submission directory. It
must finish successfully. Settings are then saved in the Git-ignored
`.env.cluster`, which the submitter loads automatically after subsequent logins.
Existing explicitly set environment variables override the saved defaults.
There is no need to activate a virtual environment or retype exports.

The short commands are:

```bash
bash junlin/setup.sh --check    # verify environments, frozen inputs and data checksums
bash junlin/setup.sh --status   # check old/new model jobs and available monitoring results
bash junlin/run.sh gemma        # restart only the four Gemma baselines
bash junlin/run.sh qwen         # restart only the two Qwen baselines, if needed
bash junlin/run.sh              # submit all six
```

`--status` requires no GPU or working serving environment. It reports both Qwen
jobs as **HEALTHY** only when each has a recorded job exit of zero, 1,800 distinct
valid monitoring units, and complete scored results for all three scopes. A log
file or a zero exit code alone does not qualify. `DONE_INVALID` means the job
finished and scored, but some verdicts were invalid; resubmission retains those
cached units. Pending/interrupted jobs, missing job status logs, and absent
scoring are reported as unconfirmed; use `squeue --me` for live queue state.
Completed monitoring units are reused when resubmitted. This does not resume
actor rollout generation.

Custom locations can be supplied to `setup.sh` (or after the filename in the
`sbatch` command): `--project-dir DIR`, `--shared-dir DIR`,
`--original-rollouts DIR`, and `--control-rollouts DIR`. Collection directories
must contain their existing `manifest.json`. The helper refuses to replace
existing data directories or install into shared storage. Its CPU checks inspect
the installed Gemma 4/unified 12B architecture and reasoning-parser registrations;
actual GPU kernels and model inference are checked when a monitor job runs.
Selected package versions, data hashes, and interpreter paths are saved in a
timestamped `$ME/logs/cluster-env-*.json` report.

### CUDA illegal-access diagnostics

If a monitoring server reports a CUDA illegal memory access, the process needs
to be restarted. [NVIDIA documents](https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/group__CUDART__TYPES.html)
that this error leaves the process in an inconsistent state. Later HTTP 500s
can therefore be a cascade from the first CUDA failure, rather than separate
problems with every request. Keep the cached outputs and inspect the first
exception in the server log.

For the Qwen3-1.7B failure, the short diagnostic command is:

```bash
bash junlin/run.sh debug
```

This submits the normal preparation step and a fresh, single-H200 server with
`--enforce-eager` and `CUDA_LAUNCH_BLOCKING=1`. Those are diagnostic options
recommended by [vLLM's troubleshooting guide](https://docs.vllm.ai/en/v0.11.0/usage/troubleshooting.html).
It runs one monitor sample, one rollout per task/variant group and one request
at a time, retaining all three observation scopes and hierarchical aggregation.
With the current collections this is 9 rollouts and 54 units. The GPU job's
default time limit is two hours, overridable with `GPU_TIME`.
Its server uses port 28475 by default, distinct from the baseline's 28474;
`PORT` can override it.

Outputs go to `$ME/runs/cuda-debug-qwen3-1.7b/` and submission logs to
`$ME/logs/cuda-debug-*/`. The baseline status checker ignores these diagnostic
receipts. Scoring is disabled; the run writes the normal verdict/node files and
a label-free summary on completion. Serving provenance records `--enforce-eager`,
and job status records synchronous-error reporting. Default baseline jobs retain
their existing serving settings.

This tests an alternative execution path and collects a more precise traceback;
success does not isolate the original cause because batching is also reduced.
For a subsequent full Qwen3-1.7B retry with eager execution, use
`bash junlin/run.sh qwen3-1.7b --eager`. It reuses finalized baseline units and
records the changed server command; eager execution can change performance, so
retain that provenance when interpreting runtime comparisons.

Transformers configuration support is checked by constructing `gemma4` and
`gemma4_unified` configurations through `AutoConfig.for_model`, with no model
weights or network access. This works when newer Transformers versions import
their registration tables from another module. If an earlier setup installed
packages successfully but failed this check, pull the corrected helper and run
`bash junlin/setup.sh` to verify and save settings without reinstalling packages.

### Manual configuration

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

Before queuing any jobs, real submissions check the installed vLLM version in
each selected serving interpreter using package metadata. A missing installation
fails with the model name, Python path, and setting to correct. This check needs
no GPU and does not load model weights or establish model/kernel compatibility.
`--dry-run` skips serving-environment checks.

```bash
export ME=/nfs/roberts/project/cpsc4880/cpsc4880_jjj49
export FRAMEWORK="$PWD"  # run from the repository root
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
16 GB RAM and four hours. GPU jobs default to `gpu_h200`, one H200, 6 CPUs,
96 GB RAM and eight hours. `ACCOUNT`, `CPU_PARTITION`, `GPU_PARTITION`,
`CPU_TIME`, `GPU_TIME`, `GPU_COUNT` and `GPU_MEM` override resources; the GPU
type stays H200. `GPU_COUNT` also sets tensor parallelism and GPU-hour accounting.
GPU jobs request six CPUs per GPU, matching the cluster allocation limit.

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

The `qwen-gemma-*` directories contain submission receipts and Slurm logs, not
monitoring results. Results go under `$ME/runs/baseline/`, outside the checkout
unless it is itself `$ME`. Each `monitor-<model>-<job>.status` log records the
results directory and the actual selected analysis/serving Python paths. Server
startup failures produce logs but no monitor verdicts or metrics.
