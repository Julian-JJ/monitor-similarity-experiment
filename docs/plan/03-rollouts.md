# Rollout generation and caching

Related: [scope](01-scope.md) · [setup](02-setup-and-architecture.md) · [evaluation](04-monitor-evaluation.md).

Proposed interface: `scripts/generate_rollouts.py --config configs/rollouts.toml`.

## Execution

For every selected environment, objective variant, and sample:

1. Reset the simulated environment to its identified initial state.
2. Run Qwen3-14B with fixed actor settings and explicit token/turn limits.
3. Save reasoning, visible assistant text, tool calls, tool responses, and final environment state in chronological order.
4. Evaluate main-task and side-objective success independently; freeze labels.
5. Branch from the completed conversation and generate the generic follow-up response with tools disabled.
6. Save follow-up reasoning and final answer separately.

Include main-task-only controls. Judge outcomes using the original objective criteria even when the actor was not instructed to pursue the side objective. Preserve refusals, timeouts, malformed tool calls, truncation, and evaluator failures as explicit statuses rather than silently discarding them.

## Generic follow-up

Store the exact generic prompt from [Monitoring Monitorability, Appendix J.2](https://arxiv.org/html/2512.18311v1#A10.SS2) as a versioned prompt asset during implementation. It asks the actor to disclose omitted decision-making details, incomplete work, and questionable behavior.

Generate one completion by default, with support for multiple independent completions branching from the same completed trajectory. Record the conversation construction and chat template, including any model-specific handling of prior reasoning.

Follow-ups must not change the evaluated environment or its frozen labels. Give follow-up generation its own cache identity so it can be added or expanded without rerunning the actor. Monitor experiments may independently reveal follow-up answers, reasoning, both, or neither.

## Artifact contract

Store raw backend responses alongside normalized, typed messages with stable message IDs. A trajectory artifact should include:

- Task ID, objective variant, sample ID, and initial-state identity.
- Environment revision, asset hashes, and prompt versions.
- Actor model revision, serving version, chat template, reasoning mode, precision/quantization, generation parameters, and requested seed.
- Ordered messages, final state, completion status, token usage, and timing.
- Main- and side-objective outcomes, scores, evaluator provenance, and any grading error.
- References to independently cached follow-up artifacts.

Requested seeds and complete metadata aid reproducibility; do not promise bitwise-identical inference across hardware/backends.

## Cache behavior

Use content-derived identities incorporating all inputs that affect the artifact.
Write completed artifacts atomically and reuse completed trajectories. Incomplete
actors are overwritten and generated again from the initial environment; do not
save partial conversations or environment checkpoints. A grading failure also
requires a fresh actor attempt. Follow-ups have separate identities and can be
retried without regenerating a completed actor. Independent regrading is future
work, not implemented in the current runner.

Frozen rollout manifests define the exact samples used in comparisons. Changing a judge or evaluator creates a new label version rather than overwriting the old one. Keep labels and privileged state available to the evaluator but outside monitor observation rendering.

## Validation milestone

Verify environment reset, reference-solution evaluation, interrupted-run restart,
absence of partial checkpoints, cache invalidation, message ordering, and
follow-up isolation. Start with one programmatic environment before generating
the full dataset.
