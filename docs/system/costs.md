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
| `wall_seconds`, `gpu_count`, `gpu_hours` | only when the run recorded its GPUs (`--gpu H200:1`); `gpu_hours = wall × GPUs / 3600` for the whole job |

Limits: `gpu_hours` is the **job's**, shared by all cells of the run, so it is a total, not a per-cell cost. Latencies include queueing behind other
concurrent requests, so they depend on `concurrency`. Dry-run estimates ([runner](runner.md)) give calls and input tokens only; output length and wall time are
unknown until a monitor runs, and the pilot is meant to measure them.
