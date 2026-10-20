"""Compute is attributed to monitors, never to cells, and a shared or unknown session is left out rather than guessed."""

import json
import unittest

from monitor_experiment import costs, pilot
from tests.support import TempDir

CELLS = [{"cell_id": "c14", "label": {"monitor": "m14"}}, {"cell_id": "c32a", "label": {"monitor": "m32"}}, {"cell_id": "c32b", "label": {"monitor": "m32"}}]


def unit(cell, finished, n):
    return {"unit_id": f"{cell}/{n}", "cell_id": cell, "finished_at": finished, "status": "complete", "hierarchical": False, "chunks": 1,
            "levels": 1, "calls": 1, "model_requests": 1, "prompt_tokens": 10, "completion_tokens": 100, "max_prompt_tokens": 10,
            "latency_seconds": 1.0, "critical_path_seconds": 1.0, "call_latencies": [1.0]}


def session(start, end, wall, job, gpus=1):
    return {"started_at": start, "finished_at": end, "wall_seconds": wall, "units_run": 1, "errors": 0,
            "compute": {"gpu_type": "H200", "gpu_count": gpus, "job_id": job}}


class AttributionTests(unittest.TestCase):
    def test_each_session_goes_to_the_monitor_whose_units_finished_in_it(self):
        manifest = {"cells": CELLS, "sessions": [session("2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+00:00", 7200, "1"),
                                                 session("2026-01-01T03:00:00+00:00", "2026-01-01T04:00:00+00:00", 3600, "2"),
                                                 session("2026-01-01T05:00:00+00:00", "2026-01-01T06:00:00+00:00", 3600, "3", gpus=2)]}
        records = [unit("c32a", "2026-01-01T01:00:00+00:00", 1), unit("c32b", "2026-01-01T01:30:00+00:00", 2),
                   unit("c14", "2026-01-01T03:30:00+00:00", 3), unit("c32a", "2026-01-01T05:30:00+00:00", 4)]
        result = costs.compute_by_monitor(manifest, records)
        self.assertEqual(result["monitors"]["m32"]["jobs"], ["1", "3"])
        self.assertEqual(result["monitors"]["m32"]["wall_seconds"], 10800)
        self.assertAlmostEqual(result["monitors"]["m32"]["gpu_hours"], 2 + 2)       # 2 h on one GPU, 1 h on two
        self.assertEqual(result["monitors"]["m14"]["gpu_hours"], 1.0)
        self.assertEqual(result["unattributed_sessions"], [])

    def test_a_session_with_two_monitors_or_none_is_listed_not_split(self):
        manifest = {"cells": CELLS, "sessions": [session("2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+00:00", 7200, "1"),
                                                 session("2026-01-01T03:00:00+00:00", "2026-01-01T04:00:00+00:00", 3600, "2")]}
        records = [unit("c32a", "2026-01-01T00:30:00+00:00", 1), unit("c14", "2026-01-01T01:00:00+00:00", 2)]
        result = costs.compute_by_monitor(manifest, records)
        self.assertEqual(result["monitors"], {})
        self.assertEqual([(u["job_id"], u["monitors"]) for u in result["unattributed_sessions"]], [("1", ["m14", "m32"]), ("2", [])])

    def test_a_cell_summary_carries_no_gpu_hours_unless_asked(self):
        self.assertIsNone(costs.summarize([unit("c14", "2026-01-01T00:00:00+00:00", 1)])["gpu_hours"])


class PilotPerMonitorTests(unittest.TestCase):
    def test_the_summary_can_be_limited_to_one_monitor_and_uses_only_its_wall_time(self):
        with TempDir() as d:
            monitors = {name: {"context_tokens": 100, "sampling": {"max_tokens": 10}} for name in ("m14", "m32")}
            manifest = {"name": "r", "cells": CELLS, "monitors": monitors,
                        "sessions": [session("2026-01-01T00:00:00+00:00", "2026-01-01T02:00:00+00:00", 7200, "1"),
                                     session("2026-01-01T03:00:00+00:00", "2026-01-01T04:00:00+00:00", 3600, "2")]}
            records = [unit("c32a", "2026-01-01T01:00:00+00:00", 1), unit("c14", "2026-01-01T03:30:00+00:00", 2)]
            (d / "manifest.json").write_text(json.dumps(manifest))
            (d / "items.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n")
            (d / "nodes.jsonl").write_text("")
            whole, one = pilot.summarize(d), pilot.summarize(d, "m14")
            self.assertEqual((whole["units"], one["units"]), (2, 1))
            self.assertEqual(one["wall_seconds"], 3600)
            self.assertEqual(one["monitor"], "m14")
            self.assertEqual(one["completion_tokens_per_second"], 100 / 3600)


if __name__ == "__main__":
    unittest.main()
