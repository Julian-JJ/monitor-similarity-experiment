"""Cost and latency of a cell, from its unit records. See docs/system/costs.md.

Dollar cost does not apply (cluster GPUs only). What is reported:

* **model_requests** and **calls**: requests including retries, and tree nodes executed;
* **prompt_tokens** and **completion_tokens**: as the server counted them;
* **served_seconds**: the sum of per-request latencies. With batching this overstates GPU time, so it
  measures load, not occupancy;
* **per-call latency** percentiles, and **critical-path** seconds per unit: the sum over tree levels of
  the slowest node, the wall time if every level's nodes ran in parallel;
* **wall_seconds** and **gpu_hours** per cell only when the caller supplies them. A run directory accumulates sessions (jobs) for several
  monitors, and a job is shared by the cells it runs, so the runner gives no wall time to any single cell; compute is reported per monitor by
  :func:`compute_by_monitor` instead.
"""


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q / 100 * (len(ordered) - 1)))]


def sessions_by_monitor(manifest, records):
    """For each recorded session, the monitors whose units finished inside its time window.

    Sessions do not record which monitor they served (one server serves one model, so each ran one), but every unit records when it
    finished, so the monitors of a session can be recovered, including for runs made before this function existed.
    """
    monitor_of = {c["cell_id"]: c["label"]["monitor"] for c in manifest["cells"]}
    out = []
    for session in manifest.get("sessions", []):
        names = {monitor_of[r["cell_id"]] for r in records
                 if r["cell_id"] in monitor_of and r.get("finished_at") and session["started_at"] <= r["finished_at"] <= session["finished_at"]}
        out.append({"session": session, "monitors": sorted(names)})
    return out


def compute_by_monitor(manifest, records):
    """Wall time and GPU-hours per monitor: the wall time of the sessions that ran only that monitor, times the session's GPU count.

    This is job time, so it includes server start-up and any idle time. A session that ran several monitors, or none, cannot be attributed
    and is listed under ``unattributed_sessions`` rather than split by guesswork.
    """
    per, unattributed = {}, []
    for entry in sessions_by_monitor(manifest, records):
        s = entry["session"]
        compute = s.get("compute") or {}
        if len(entry["monitors"]) != 1:
            unattributed.append({"job_id": compute.get("job_id"), "wall_seconds": s["wall_seconds"], "monitors": entry["monitors"]})
            continue
        row = per.setdefault(entry["monitors"][0], {"wall_seconds": 0.0, "gpu_hours": 0.0, "gpu_type": None, "jobs": [], "units_run": 0})
        row["wall_seconds"] += s["wall_seconds"]
        row["units_run"] += s.get("units_run", 0)
        row["jobs"].append(compute.get("job_id"))
        row["gpu_type"] = compute.get("gpu_type")
        gpus = compute.get("gpu_count")
        row["gpu_hours"] = None if (gpus is None or row["gpu_hours"] is None) else row["gpu_hours"] + s["wall_seconds"] * gpus / 3600
    return {"monitors": per, "unattributed_sessions": unattributed}


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
