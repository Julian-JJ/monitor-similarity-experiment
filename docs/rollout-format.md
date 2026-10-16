# Cached rollout format (v1)

Artifacts are UTF-8 JSON. Paths below are relative to the configured cache root.
Readers should check `schema_version`, `artifact_type`, and `status` before use.

| Path | Contents |
| --- | --- |
| `rollouts/<task>/<variant>/<id>.json` | Actor trajectory, checkpoint, and frozen outcome labels |
| `followups/<actor-id>/<id>.json` | One independent follow-up completion |
| `entries/<actor-id>.json` | Actor/follow-up paths for one fully generated sample |
| `manifests/<id>.json` | The ordered sample entries for a completed invocation |

IDs are SHA-256 hashes of canonical JSON identities. Actor identity includes
model revision, serving metadata, generation parameters, task/variant/sample,
requested seed, actual environment source hash, dependency versions, and runner
implementation hash. Follow-up identity includes the parent artifact hash,
question, generation settings, seed, and sample index. Endpoint credentials are
never included. Changing behavior-affecting inputs creates new artifacts.

## Actor fields

- `identity`, `rollout_id`, `schema_version`, `artifact_type`.
- `status`: `running`, `error`, or `complete`; `error` describes a failed stage.
- `termination`: `end_task`, `final_answer`, or `max_turns`.
- `messages`: ordered messages with stable `m00000`-style IDs.
- `raw_responses`: original successful chat-completion responses, including
  server usage counters and finish reasons. Rejected truncated/missing-reasoning
  responses are retained under `failed_responses`.
- `initial_state`, `initial_state_hash`, `final_state`, and `random_state`.
- `turns`, `elapsed_seconds`, `created_at`, and `updated_at`.
- `evaluation`: programmatic raw main score, parsed score, threshold, main
  success, both side-objective labels, and the selected target's `side_success`.

For `main_only`, selected `side_success` is null; use the explicitly named
`evaluation.side.benign` or `.malicious` label for the relevant comparison.
`complete` means execution and grading finished, including an explicit
`max_turns` stop; it does not mean either objective succeeded. A failed grading
attempt retains the finished actor state, so retrying need not rerun inference.

## Message fields

All messages contain `id`, `role`, and `content`. Assistant messages additionally
contain `reasoning`, `tool_calls`, and `finish_reason`. Calls use the standard
chat-completion shape: `id`, `type="function"`, and
`function={name, arguments}` with JSON-encoded argument strings. Tool replies
contain `tool_call_id`, `name`, and `error` (null on runtime success).

Reasoning is separate from visible text. Original system prompts may contain
the hidden side objective; future observation renderers must not expose them
automatically. Initial/final state and evaluator labels are privileged grading
data, not monitor observations.

## Follow-up fields and resume

Follow-up artifacts contain their `identity`, `parent_rollout_id`, `question`,
normalized assistant `response`, `raw_response`, `status`, and timing. Parent
messages are referenced rather than duplicated. Each completion starts from the
same parent conversation; no follow-up tools are executed and frozen labels do
not change.

Writes are atomic and actor artifacts are locked across generation and
follow-up stages. Resume restores committed JSON state and the simulation RNG;
it does not replay real-world side effects. Model seeds are recorded per request
(actor seed plus turn index; follow-up seed plus sample index), without claiming
bitwise reproducibility across GPUs or backend versions.
