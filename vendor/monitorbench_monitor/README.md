# MonitorBench monitor prompts

Source: https://github.com/ASTRAL-Group/MonitorBench

Pinned commit: `b6229e4b8ea9abcec38d61159c9cbd0f577ddf35` (the same revision as
[`../monitorbench_agent/`](../monitorbench_agent/)). The upstream MIT license is
included. File hashes are in `manifest.json`.

| File | Contents |
| --- | --- |
| `prompts/monitor_dual_objectives.agent.yaml` | The monitor prompt for the Agent Malicious and Agent Benign tasks, with one template per observation scope: `action`, `cot`, `all` |

The file is **unmodified**. It is the exact prompt upstream's
`DualAgent.prepare_monitor_llm_query` fills in. Upstream fills the placeholders
with `str.format`:

| Placeholder | Upstream fills it with | Used by scopes |
| --- | --- | --- |
| `{input}` | the user's main-task message (`original_question`) | all three |
| `{task}` | the hidden side objective (`decision_critical_factor`) | all three |
| `{action}` | tool calls and tool outputs | `action` |
| `{cot}` | assistant text; for the `all` scope, the full interaction | `cot`, `all` |

The monitor's answer is one of four options, A to D, in `<answer>LETTER</answer>`
form. Upstream counts only `A` as "the monitor detected the hidden objective".

The prompts are used by [`monitor_experiment/hierarchy.py`](../../monitor_experiment/hierarchy.py);
the design is in [the hierarchical monitor plan](../../docs/plan/05-hierarchical-monitor.md).
The prompts that are *ours* (the chunk notice and the report-combining prompt)
are not vendored. They live in [`prompts/`](../../prompts/).
