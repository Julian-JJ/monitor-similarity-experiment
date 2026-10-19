"""Cost and latency of a cell, from its unit records. See docs/system/costs.md.

Dollar cost does not apply (cluster GPUs only). What is reported:

* **model_requests** and **calls**: requests including retries, and tree nodes executed;
* **prompt_tokens** and **completion_tokens**: as the server counted them;
* **served_seconds**: the sum of per-request latencies. With batching this overstates GPU time, so it
  measures load, not occupancy;
* **per-call latency** percentiles, and **critical-path** seconds per unit: the sum over tree levels of
  the slowest node, the wall time if every level's nodes ran in parallel;
* **wall_seconds** and **gpu_hours** only when the run supplied them (job wall time times GPU count).
"""


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q / 100 * (len(ordered) - 1)))]


def summarize(records, wall_seconds=None, gpu_count=None):
    paths = [r.get("critical_path_seconds") or 0.0 for r in records]
    latencies = [x for r in records for x in (r.get("call_latencies") or [])]
    statuses = {}
    for r in records:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    out = {"units": len(records), "units_by_status": statuses,
           "hierarchical_units": sum(1 for r in records if r.get("hierarchical")),
           "calls": sum(r.get("calls", 0) for r in records),
           "model_requests": sum(r.get("model_requests", 0) for r in records),
           "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in records),
           "completion_tokens": sum(r.get("completion_tokens", 0) for r in records),
           "served_seconds": sum(r.get("latency_seconds", 0.0) for r in records),
           "call_latency_p50": percentile(latencies, 50), "call_latency_p95": percentile(latencies, 95),
           "critical_path_mean": (sum(paths) / len(paths)) if paths else None,
           "critical_path_p95": percentile(paths, 95), "critical_path_max": max(paths) if paths else None,
           "max_prompt_tokens": max([r.get("max_prompt_tokens") or 0 for r in records], default=0),
           "wall_seconds": wall_seconds, "gpu_count": gpu_count,
           "gpu_hours": (wall_seconds * gpu_count / 3600) if wall_seconds is not None and gpu_count else None}
    return out
