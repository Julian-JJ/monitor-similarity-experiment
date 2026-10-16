# Monitor similarity experiments

A lightweight runner for cached **Qwen3-14B** trajectories in MonitorBench's
code-verifiable dual-objective agent tasks. This implementation covers setup,
model download, actor rollouts, programmatic grading, and generic follow-ups.
Monitor evaluation and hierarchical aggregation remain planned work.

## Cluster quick start

Clone this repository on the cluster. Use Python 3.11+ (Python 3.11/3.12 is a
practical choice for GPU serving), Git, and a CUDA environment supported by your
chosen vLLM release. No weights or GPU packages are included in the repository.

```bash
bash scripts/setup.sh --with-serving
source .venv/bin/activate
python scripts/download_model.py
```

Setup installs the small environment dependencies and optional vLLM backend,
then checks all three environments without inference. Model download is a
separate explicit step. The downloader resolves the requested revision to an
immutable Hugging Face commit, resumes existing downloads, and records a
manifest. Use `--revision COMMIT` to reproduce an earlier download.

Start the server on an allocated GPU node:

```bash
python scripts/serve_model.py --tensor-parallel-size 1
```

The serving script uses BF16, Qwen3 reasoning extraction, Hermes tool parsing,
and a 32,768-token context. Adjust GPU count with `--tensor-parallel-size` and
context capacity with `--max-model-len`. BF16 weights alone require roughly
28–30 GB; context and runtime allocations require additional GPU memory. Actual
GPU inference must be validated on the target cluster.

For tasks whose histories exceed the native context, explicitly enable YaRN,
following the [Qwen long-context guidance](https://huggingface.co/Qwen/Qwen3-14B#processing-long-texts):

```bash
python scripts/serve_model.py --tensor-parallel-size 2 --max-model-len 65536 --yarn-factor 2
```

Context overflow is saved as an error rather than truncating the trajectory.
Changing context/scaling changes actor behavior and creates a different cache
identity through the serving manifest.

In another terminal/job that can reach the server:

```bash
source .venv/bin/activate
python scripts/generate_rollouts.py --tasks bank_transfer_2 --variants benign --samples 1
```

The full default run is:

```bash
python scripts/generate_rollouts.py
```

This runs 8 samples for each of 3 tasks × 2 objective variants (48 actor
trajectories), with one generic follow-up completion per trajectory. The
[MonitorBench configuration](https://github.com/ASTRAL-Group/MonitorBench/blob/b6229e4b8ea9abcec38d61159c9cbd0f577ddf35/config/vllm_config.yaml)
sets **8 actor rollouts per prompt**, 1 verification sample, and 4 monitor
samples. These are checked-in defaults, not a claim about every published run.

## Task selection and settings

Supported tasks, with both benign and malicious side objectives:

- `bank_transfer_2`
- `american_airlines_2`
- `spam_filter_update`

Expenditure Accounting and API Key Calendar Agendas are excluded because their
main-task checks and benign side-task checks use LLM judges. The included tasks
use simulated tools and cached environment assets; they do not send real money,
book real tickets, or send real emails.

Edit [configs/rollouts.toml](configs/rollouts.toml) to set generation limits,
endpoint, paths, and sample counts. Repository-relative paths work regardless of
the shell's current directory. Custom download paths must also be supplied to
the serving script and configured in the rollout TOML. For a separate serving
environment, run setup without `--with-serving`, then install
`requirements-serving.txt` there.

Useful overrides:

```bash
python scripts/generate_rollouts.py --tasks spam_filter_update --variants benign malicious --samples 8
python scripts/generate_rollouts.py --variants main_only --samples 8
python scripts/generate_rollouts.py --followup-samples 3
python scripts/generate_rollouts.py --base-url http://gpu-node:8000/v1
python scripts/generate_rollouts.py --start-sample 8 --samples 8
python scripts/generate_rollouts.py --check-environments
```

`main_only` omits the side objective from actor instructions and records both
side-objective outcome labels. Use these separately as controls. Follow-up
samples branch independently from the completed actor conversation, with tools
disabled. Prior reasoning is retained in artifacts; the Qwen chat history sends
visible content and calls, consistent with its native template behavior.

For multi-node jobs, share model manifests and cache storage, set the server's
`--host` appropriately, and configure the reachable URL. Serving provenance is
read from the manifest written by `serve_model.py`; the client verifies the
served model name but cannot remotely attest the weights. Keep that manifest
paired with the actual server. Optional authentication reads `MODEL_API_KEY` (or
the configured environment-variable name) without storing its value in cache.

## Cache and verification

Completed artifacts are reused. Actor state, messages, and simulation RNG are
checkpointed after each turn, allowing interrupted runs to resume. Increasing
the follow-up sample count does not regenerate actor trajectories. Sample
ranges support separate cluster jobs; file locks prevent simultaneous writes
to the same actor artifact.

The runner saves raw responses, reasoning separately from visible content,
tool calls/results, initial/final state, model/environment provenance, and
independent main/side outcome labels. It rejects truncated generations or
missing reasoning by default. A turn-limit termination is recorded explicitly,
graded on its final state, and retained rather than silently dropped.

See [the artifact format](docs/rollout-format.md) for paths and schema, and
[vendor notes](vendor/README.md) for preserved upstream evaluator limitations
and explicit main-score threshold choices. In particular, the upstream spam
main evaluator can already pass on the initial environment; interpret the
recorded criterion rather than assuming it proves every requested action.

Run offline tests with environment dependencies installed:

```bash
python -m unittest discover -s tests -v
```

Tests exercise real simulated tools/evaluators and deterministic fake model
responses, including interruption recovery and follow-up isolation. They do not
download weights or establish GPU inference compatibility.

The broader [implementation plan](docs/plan/01-scope.md) describes future monitor
experiments. [Monitoring Monitorability](https://arxiv.org/html/2512.18311v1)
supplies the generic follow-up prompt; [MonitorBench](https://arxiv.org/html/2603.28590v1)
supplies the environments. Upstream source revisions, modifications, and MIT
licenses are included under `vendor/`.
