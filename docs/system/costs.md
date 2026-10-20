# Cost and latency

Code: [`monitor_experiment/costs.py`](../../monitor_experiment/costs.py); records come from [`runner.py`](../../monitor_experiment/runner.py).
Compute is cluster GPUs only, so **dollars do not apply** ([07 section 2.6](../plan/07-design-decisions.md#26-compute)).

`summarize(records, wall_seconds, gpu_count)` returns, per cell:

| Field | Meaning and caveat |
| --- | --- |
| `units`, `units_by_status`, `hierarchical_units` | how many units, with which status, and how many used the chunked tree |
| `calls` | tree nodes executed |
| `model_requests` | requests including retries |
| `prompt_tokens`, `completion_tokens` | as the server counted them (the monitor's own tokenizer) |
| `max_prompt_tokens` | the largest single prompt the server saw; compare with the monitor's context minus its reply limit |
| `served_seconds` | the **sum** of request latencies. With batching this overstates GPU time; it measures load, not occupancy |
| `call_latency_p50`, `call_latency_p95` | per-request latency percentiles |
| `critical_path_mean`, `_p95`, `_max` | per unit, the sum over tree levels of the slowest node: the wall time if every level's nodes ran in parallel. Councils take the slowest member |
| `wall_seconds`, `gpu_count`, `gpu_hours` | only when a caller supplies them; the runner does **not**, because a job is shared by the cells it runs. See *Compute per monitor* below |

**Compute per monitor** (`compute_by_monitor(manifest, records)`, written into `metrics.json` and printed in the report): each recorded session is assigned to the monitor whose units finished inside its time window
(`sessions_by_monitor`), and a monitor's wall time and GPU-hours are the sum over its sessions, times the GPU count. This is job time, so it includes server start-up and idle time. A session with units from more than one monitor, or from none,
is listed as unattributed, never split. Earlier versions printed the whole run's GPU-hours on every cell, which was wrong as soon as a run held two monitors (found 2026-10-20: 8.86 on all six cells of `baseline`).

Limits: Latencies include queueing behind other
concurrent requests, so they depend on `concurrency`. Dry-run estimates ([runner](runner.md)) give calls and input tokens only; output length and wall time are
unknown until a monitor runs, and the pilot is meant to measure them.
