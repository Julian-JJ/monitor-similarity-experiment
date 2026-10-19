# Cluster runbook (Phase B)

Scripts: `mihai/cluster/setup_cluster.sh`, `run_controls.sbatch`, `run_monitor.sbatch`; helpers `scripts/prepare_controls.py`,
`scripts/serve_monitor.py`, `scripts/build_collection.py`. Code: `monitor_experiment/{control_setup,monitor_serving,collection_builder}.py`.
Tests: `tests/test_control_setup.py`, `test_monitor_serving.py`, `test_collection_builder.py`, `test_cluster_scripts.py`.

**Status (2026-10-19): written and tested locally; not yet run on the cluster.** The SSH connection had expired and needs your passphrase and MFA, which
the assistant cannot supply. Everything below the first section is a plan whose commands have not been executed there.

## What is known about the cluster and the existing tooling

Verified by reading the existing scripts or by earlier commands in this project:

* The original launch script (`mihai/cluster/run_qwen.sbatch`) **hard-codes the teammate's project directory** (`…/cpsc4880_mae73`) for logs, caches, locks and outputs, and
  sets read permissions for teammates with `setfacl`. Your account cannot write there. The new scripts use variables whose defaults are your own directory
  (`…/cpsc4880_as4833`) and never write under the teammate's; a test enforces this.
* `scripts/serve_model.py` writes `serving-manifest.json` **into the model directory**. The shared Qwen3-14B directory is not writable by you, so the controls
  use a private directory of symlinks to the shared weights with an identical copy of the download manifest.
* The launch scripts require the git checkout to match a commit and be unmodified (`git diff --quiet HEAD -- scripts monitor_experiment vendor configs prompts requirements*.txt`), and
  an actor's cache identity hashes every `*.py` in `monitor_experiment/`. **Commit `5dc0417` reproduces the cached batch's recorded implementation hash exactly
  (`8542b29e…`)**; the two earlier commits and the current branch do not (the branch has new modules). So the controls must be generated from a pristine `5dc0417`
  checkout. The cluster already has one, clean, at `~/project_cpsc4880/cpsc4880_as4833/monitor-similarity-experiment` (cloned and copied on 2026-10-19; origin has no credentials).
* The shared Python environments (`$SHARED/envs/monitor-research`, `monitor-vllm`) and the shared weights were readable and executable by your account in earlier commands.
* The project filesystem is slow (copying 8 MB took about 15 minutes); the scheduler limit noted in the repository is six hours.

**Not known** and needed before submitting: the partition, account, GPU resource name (for example `gpu:h200:1`) and time limit for an H200 job. The teammate's
submission receipts under `$SHARED/logs/` probably contain them; if they are not readable, ask the course staff or check `sinfo` and `sacctmgr`.

## Layout on the cluster (`ME=/nfs/roberts/project/cpsc4880/cpsc4880_as4833`)

| Path | What | Written by |
| --- | --- | --- |
| `$ME/monitor-similarity-experiment/` | **pristine `5dc0417`**, used only to generate controls; `models` and `cache` are links into `$ME` | already there; `setup_cluster.sh` adds the links |
| `$ME/monitor-framework/` | this branch, copied with `rsync` (the cluster checkout cannot pull from GitHub) | you / the assistant |
| `$ME/models/qwen3-14b/` | symlinks to the shared weights, a copy of the download manifest, and the serving manifest the server writes | `setup_cluster.sh`, `serve_model.py` |
| `$ME/models/<monitor>/` | other monitors' weights, when downloaded | `scripts/download_model.py`-style download (not yet written for monitors) |
| `$ME/cache/` | rollout cache, vLLM/HF caches | the jobs |
| `$ME/configs/rollouts-main-only.toml` | derived control config | `setup_cluster.sh` |
| `$ME/envs/monitor-analysis/` | Python with PyYAML, tokenizers, pydantic, pandas for the runner | `setup_cluster.sh` |
| `$ME/logs/`, `$ME/runs/` | job logs and status files; run directories | the jobs |
| `$ME/rollouts_main_only_clean/` | the control collection | `scripts/build_collection.py` |

## Runbook

**B1. Copy the branch (from your Mac)**, excluding data and the environment:

```bash
rsync -a --exclude .venv --exclude cache --exclude rollouts_original_clean --exclude runs --exclude presence --exclude .git \
  -e "ssh -o ControlPath=$HOME/.ssh/cm-%r@%h:%p" ./ cpsc4880_as4833@bouchet.ycrc.yale.edu:/nfs/roberts/project/cpsc4880/cpsc4880_as4833/monitor-framework/
```

**Setup (login node, once):** `bash $ME/monitor-framework/mihai/cluster/setup_cluster.sh`. It builds the private model directory, links the data, derives the config, **verifies that the
checkout reproduces the cached batch's implementation hash**, and creates the analysis environment. Any failed check stops it with a message.

**B2. Controls.** Submit `run_controls.sbatch` with one H200 (options as in the script header). It serves Qwen3-14B exactly as the cached batch was served (one GPU, 131,072 context,
YaRN 4), runs six workers (two blocks of six samples for each of three tasks, 36 rollouts), and writes the cache. The stopping rule in
[the decisions](../plan/07-design-decisions.md#211-control-rollouts): at least 8 retained per task; if fewer, rerun with `FIRST_SAMPLE=12` (and so on, up to 20 per task).
Completed samples are cached and reused, so a job that hits the time limit is simply resubmitted. Then:

```bash
python $ME/monitor-framework/scripts/build_collection.py --cache $ME/cache --out $ME/rollouts_main_only_clean --name main_only_v1 \
    --expect 12 --source-job $JOBID --hardware "H200 x1" --config $ME/configs/rollouts-main-only.toml
```

The retention rule is execution status only, never labels. Copy the collection (about 100 MB) to your Mac, or link it as `rollouts_main_only_clean` in the framework copy, for scoring.

**B3. Pilot (format only).** Qwen3-14B is already installed: `MONITOR=qwen3-14b EXPERIMENT=configs/experiments/pilot-format-only.toml MODEL_DIR=$ME/models/qwen3-14b SCORE=0 sbatch … run_monitor.sbatch`.
`SCORE=0` keeps the job from reading any label. The job ends by writing `pilot-summary.json` with `scripts/pilot_summary.py`: validity, retries, finish reasons, reply and plan lengths, prompt sizes
against the input limit, latency and throughput, from `items.jsonl`, `nodes.jsonl` and `plans/` only (a test checks that the module cannot reach labels). Judge the prompts by that and nothing else;
wording changes are format fixes and are logged. When satisfied, `python scripts/freeze.py write --status frozen` and commit.

**B4. Another monitor.** Download its weights into `$ME/models/<name>/` (Qwen3-32B is about 65 GB; check the quota first), pin the revision in `configs/monitors.toml`, set `verified = true`, then submit
`run_monitor.sbatch` with `MONITOR=qwen3-32b` and `TP` as needed. A 32B model in BF16 fits one 141 GB H200 but not one 48 GB A40.

**B5. Baseline** `configs/experiments/baseline.toml` with Qwen3-32B, then score, compare and report ([cli](cli.md)).

## What each job records

`$ME/logs/controls-<job>.status` and `monitor-<monitor>-<job>.status` hold the verification output, GPU model, config hash, worker assignments and exit status; server logs are alongside.
`serving-<monitor>-<job>.json` records the vLLM command, version and the monitor's identity. A run directory's manifest records the served model name, the GPU count and the job id.

## Not verified (will be learned on first use)

* The Slurm options above. * That the shared environments run vLLM on a compute node under your account. * The `--reasoning-parser` name for GPT-OSS and Gemma (left unset), and `--dtype auto`
for them. * That the server accepts `reasoning_effort` for GPT-OSS. * That `pip install` works from a login node (needed for the analysis environment). * Real generation speed: the dry run cannot
know it, and the pilot is meant to measure it, after which wall-time estimates become possible. * That control transcripts are as long as the cached ones (cost scaling assumes so).
