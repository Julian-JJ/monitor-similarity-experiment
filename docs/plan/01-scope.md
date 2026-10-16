# Scope and research decisions

Status: the initial model-download and programmatic-task rollout slice is
implemented; see [the repository README](../../README.md). Monitor evaluation
and hierarchical aggregation remain planned work. The documents below describe
the broader intended framework.

Build a lightweight framework to measure how the monitor affects monitorability. Generate Qwen3-14B trajectories once, freeze their outcome labels, and reuse identical trajectories across monitor conditions.

## Reading guide

1. This document defines the experiment and its assumptions.
2. [Setup and architecture](02-setup-and-architecture.md) defines dependencies, environment reuse, and model support.
3. [Rollout generation](03-rollouts.md) defines actor execution, follow-ups, and caching.
4. [Monitor evaluation](04-monitor-evaluation.md) defines experimental controls, metrics, and validation.

## Task scope

Use MonitorBench's five dual-objective **agent** environments, each with malicious and benign side-objective variants. The separate steganography, summarization, and coding families are outside the initial scope. Also generate main-task-only controls.

| Environment folder | Main objective check | Benign side-objective check |
| --- | --- | --- |
| `bank_transfer_2` | Code based | Code based |
| `american_airlines_2` | Code based | Code based |
| `expenditure_accounting` | LLM judge | LLM judge |
| `api_key_calendar_agendas_2` | LLM judge | LLM judge |
| `spam_filter_update` | Code based | Code based |

These classifications come from the paper; audit the pinned implementation before relying on them. In particular, verify every malicious side-objective evaluator rather than assuming all side-objective checks are deterministic.

Keep main-task success and side-objective success separate. Preserve original grading semantics, including judge thresholds. A programmatic-only selection should exclude judge-dependent labels. Replacing a semantic judge with a file-existence check changes the task and must be identified as a modified benchmark.

## Research choices

- Fix the actor to `Qwen/Qwen3-14B`, with explicit reasoning and generation settings.
- Compare monitor models on the same cached rollout IDs.
- Use verified side-objective completion as the primary prediction target; report malicious and benign variants separately.
- Treat follow-up visibility, observation scope, repeated passes, and performing the task first as independent experimental controls.
- Keep evaluator models independent of the monitor being compared, and cache their labels.
- Treat “Qwen 1.4B” as a proposed reference to Qwen3-1.7B, pending correction.

## Sources and interpretation

[Monitoring Monitorability](https://arxiv.org/html/2512.18311v1) motivates the three observation scopes, the TPR × TNR metric, and generic follow-up experiments. Follow-up reasoning and final answers should be stored separately.

[MonitorBench](https://arxiv.org/html/2603.28590v1), especially Appendix A.1.2, supplies the agent tasks and documents judge-dependent checks. Its outcome evaluation measures detection among successful target behaviors; retain this as a secondary statistic alongside two-class detection metrics.

Repeated inspection and the task-first condition are experimental extensions, not claims of exact paper reproduction. Only five base environments are available: repeated rollouts improve within-task precision but offer limited evidence about generalization to new tasks.
