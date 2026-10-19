# Cluster runbook (Phase B)

Scripts: `mihai/cluster/setup_cluster.sh`, `run_controls.sbatch`, `run_monitor.sbatch`; helpers `scripts/prepare_controls.py`,
`scripts/serve_monitor.py`, `scripts/build_collection.py`. Code: `monitor_experiment/{control_setup,monitor_serving,collection_builder}.py`.
Tests: `tests/test_control_setup.py`, `test_monitor_serving.py`, `test_collection_builder.py`, `test_cluster_scripts.py`.

**Status (2026-10-19, updated): B1 to B3 have been run on the cluster; the control rollouts are generating.** Sections below mark what has been *verified by running it* and what has not.
The SSH connection must be opened by you (passphrase and MFA) and expires; the assistant cannot supply those.

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

**Slurm settings (learned on 2026-10-19):** account `cpsc4880`, QOS `normal`; partition `gpu_h200` accepts all accounts and has no maximum time; the flags that work (from the teammate's readable submission
records and confirmed by jobs 30068171 and 30068179) are `--account=cpsc4880 --partition=gpu_h200 --nodes=1 --ntasks=1 --gpus=h200:1 --cpus-per-task=8 --mem=96G --no-requeue`, with a time limit chosen per job.
The earlier H200 job needed about 2¼ hours for 30 pairs; the A40 pair (`gpu_devel`, 2×a40) hit its 6-hour limit. Other GPU partitions exist (`gpu_h100`, `gpu_b200`, `gpu_rtx6000`, `gpu`); they have not been used.
`sbatch --test-only` reports a start time exactly one year ahead for every GPU partition: that is the end of a 365-day `EmergencyMaintenance` reservation on other nodes, not a real wait. The queues are long
(hundreds pending per partition) but jobs submitted to `gpu_h200` started within seconds because GPUs were free. Check `sinfo`/`scontrol show node` for free GPUs, and read `squeue --me` after submitting.

## Layout on the cluster (`ME=/nfs/roberts/project/cpsc4880/cpsc4880_as4833`)

| Path | What | Written by |
| --- | --- | --- |
| `$ME/monitor-similarity-experiment/` | **pristine `5dc0417`**, used only to generate controls; `models` and `cache` are links into `$ME` | already there; `setup_cluster.sh` adds the links |
| `$ME/monitor-framework/` | this branch, copied with `rsync` (the cluster checkout cannot pull from GitHub) | you / the assistant |
| `$ME/models/qwen3-14b/` | symlinks to the shared weights, a copy of the download manifest, and the serving manifest the server writes | `setup_cluster.sh`, `serve_model.py` |
| `$ME/models/<monitor>/` | other monitors' weights, when downloaded | `scripts/download_model.py`-style download (not yet written for monitors) |
| `$ME/cache/` | rollout cache, vLLM/HF caches | the jobs |
| `$ME/logs/controls-pairs-<job>/` | one log per (task, sample) and `summary.json` | `run_pairs.py` |
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
YaRN 4), then runs `scripts/run_pairs.py`: **one process per (task, sample), eight at a time** (36 rollouts), skipping samples already complete in the cache, and writes the cache.
One process per pair matters: `generate_rollouts.py` stops its whole process at the first execution failure, so an earlier design that gave each process a block of six samples would lose the
rest of a block whenever one sample failed (the first control job showed this within half an hour: see the work log). The stopping rule in
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

## Verified by running it (2026-10-19)

* The Slurm flags above; the shared environments run vLLM on a compute node under your account; `pip install` works from a login node.
* The setup script end to end (18 minutes on the slow filesystem), including **the pristine checkout reproducing the cached batch's implementation hash on the cluster**, and the environment self-test (71, 73 and 41 tools, matching the `ast` extraction).
* `serve_monitor.py` with Qwen3-14B: the server became ready in about 85 seconds; `--reasoning-parser qwen3` returns the thinking separately; the client's request, `chat_template_kwargs`, `usage` fields and served-name check all worked against a real vLLM server.
* The format-only pilot (below).

### What the pilot measured (job 30068179; Qwen3-14B as monitor, 48 units, run alongside the control job on the same node)

| Quantity | Value |
| --- | --- |
| requests / invalid / retried / not a normal stop | 352 / 0 / 0 / 0 |
| completion tokens per request (thinking plus reply) | median 997, 95th percentile 1,698, max 3,189 (the cap is 16,768) |
| reply length | median 1,931 characters |
| prompt tokens per request | median 11,003, max 14,243 (limit 15,488) |
| plans | 9; 330 to 474 words (limit 600), 524 to 870 tokens (limit 1,000); none needed a retry |
| chunks per unit / tree levels | median 6, max 23 / median 2, max 3 |
| latency per request | median 15 s, 95th percentile 27 s |
| throughput at concurrency 8 | 405 completion tokens per second; 911 s wall time for 352 requests |

Two consequences. The planning assumption of about 1,000 tokens per monitor reply was right. And **wall time is the constraint**: at this one measured rate (small model, concurrency 8) the baseline's
8,336 calls would take roughly 6 hours and the full grid's 100,128 calls roughly 70 hours on one server; larger monitors are slower and more concurrency should be faster, but neither has been measured.

**A plan-prompt observation (not acted on).** All nine plans mention actions that are unneeded, unusual or to be avoided, but only two give them their own heading (item 3 of the plan prompt). The
pre-registered rule allows wording changes only for format failures, and this is not one, so the wording was left alone and the prompts were frozen.

## Not verified yet

* The `--reasoning-parser` name for GPT-OSS and Gemma (left unset), and `--dtype auto` for them. * That the server accepts `reasoning_effort` for GPT-OSS. * That Qwen3-32B in BF16 fits and runs on one H200 at
the 32,768 context. * Throughput at higher concurrency and for larger monitors. * That the collection builder works on real control output (it is tested on a real generator cache, not on this run's).
