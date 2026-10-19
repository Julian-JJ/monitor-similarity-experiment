# Setup and architecture

Related: [scope](01-scope.md) · [rollouts](03-rollouts.md) · [evaluation](04-monitor-evaluation.md).

## Minimal framework

Use Python 3.11+, standard-library argument parsing, TOML configuration, JSON/JSONL artifacts, and CSV reports. Avoid a mandatory database, tracking service, agent orchestration framework, or plotting stack.

Expose three entry points:

| Entry point | Responsibility |
| --- | --- |
| `scripts/setup.sh` | Install selected dependencies, fetch environments, and check readiness |
| `scripts/generate_rollouts.py` | Execute and label actor trajectories; cache follow-ups |
| `scripts/run_experiment.py` | Run or price a monitor experiment on cached trajectories (**built**, offline-tested; replaces the proposed `run_monitors.py`); with `score_run.py`, `compare_cells.py`, `make_report.py` ([system docs](../system/cli.md)) |

Offline helpers that already exist: `scripts/count_transcript_tokens.py` (which
single-pass monitor prompts fit a context window) and `scripts/plan_hierarchy.py`
(a dry run of the [hierarchical monitor](05-hierarchical-monitor.md): chunks, model
calls, token totals). They need `requirements-analysis.txt`, not a GPU.
Keep implementation in a compact Python package, with separate environment adapters, inference adapters, artifact handling, observation rendering, and metrics. Observation rendering, chunking and tree execution for the monitor are in `monitor_experiment/hierarchy.py`; metrics are not yet implemented. Store example TOML configurations and versioned prompt assets in the repository.

## Environment reuse

Provisionally extract the required environment code and assets from a pinned [MonitorBench revision](https://github.com/ASTRAL-Group/MonitorBench), preserving applicable licenses and attribution. Reuse task definitions, tools, initial state, and evaluators; write our own rollout and monitoring loops.

The upstream agent runner has global import/configuration coupling. Audit the dependency closure before finalizing extraction; reuse the full runner only if it is demonstrably simpler without importing the full dependency stack.

Create a manifest recording task/variant, assets, dependencies, evaluator types, judge model and thresholds, upstream revision, and local modifications. Run tools against simulated environments, including fresh copies for monitor task attempts.

## Inference and model registry

The core runner uses a configurable HTTP inference endpoint. Provide a separately installed, pinned vLLM serving environment as an optional local backend. Existing endpoints should work without GPU libraries in the runner.

Adapters handle reasoning fields, tool calls, chat templates, context limits, and model-specific generation settings. Reject unsupported capabilities explicitly, including a CoT condition on an endpoint that does not expose reasoning.

| Role/family | Proposed identifiers |
| --- | --- |
| Actor | `Qwen/Qwen3-14B` |
| Qwen monitors | `Qwen/Qwen3-1.7B`, `Qwen/Qwen3-4B`, `Qwen/Qwen3-14B`, `Qwen/Qwen3-32B` |
| GPT-OSS monitor | `openai/gpt-oss-120b` |
| Gemma monitors | `google/gemma-4-E2B-it`, `google/gemma-4-E4B-it`, `google/gemma-4-12B-it`, `google/gemma-4-31B-it` |

Pin exact model revisions and validate serving compatibility during implementation. Allow custom identifiers/endpoints. Record precision and quantization as part of every condition. References: [Qwen3-14B](https://huggingface.co/Qwen/Qwen3-14B), [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B), [GPT-OSS-120B](https://huggingface.co/openai/gpt-oss-120b), [Gemma 4 overview](https://ai.google.dev/gemma/docs/core).

## Setup behavior

`setup.sh` should create a virtual environment, install pinned dependencies, fetch pinned environment assets with hash checks, and optionally install local serving dependencies/download selected weights. Reuse existing weight caches; do not download all monitor models by default.

Make setup repeatable. Print a readiness report covering credentials where needed, endpoint connectivity, tool calling, reasoning extraction, and context limits. Heavy model serving remains an optional dependency even though actual inference requires a working backend.

## First implementation milestones

1. Audit and pin environment dependencies and evaluators; replay reference solutions.
2. Implement setup and adapters; verify tool calls and reasoning extraction with a small live request.
3. Proceed to [rollout generation](03-rollouts.md), then [monitor evaluation](04-monitor-evaluation.md).
