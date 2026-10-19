"""The label-free pilot summary."""

import inspect
import json
import unittest
from pathlib import Path

from monitor_experiment import hierarchy as h
from monitor_experiment import pilot, runner
from monitor_experiment import spec as sp
from tests.support import TempDir, make_project
from tests.test_runner import FakeMonitor, lines, run, spec_for


class PilotTests(unittest.TestCase):
    def test_summary_of_a_run_with_plans_and_an_invalid_reply(self):
        with TempDir() as root:
            registry = make_project(root)
            spec = spec_for(grid={"scope": ["cot"], "task_context": ["none", "plan"]})
            run_dir = run(root, registry, spec, FakeMonitor(invalid_if=lambda p: "TAGbenign1" in p))
            summary = pilot.summarize(run_dir)
            items = lines(run_dir / "items.jsonl")
            self.assertEqual(summary["units"], len(items))
            self.assertEqual(summary["units_by_status"], {"complete": sum(r["status"] == "complete" for r in items),
                                                         "invalid": sum(r["status"] == "invalid" for r in items)})
            self.assertGreater(summary["invalid_requests"], 0)
            self.assertEqual(summary["invalid_reasons"], {"no <answer>A-D</answer> in the response": summary["invalid_requests"]})
            self.assertEqual(summary["finish_reasons"], {"stop": summary["requests"]})
            self.assertEqual(summary["plans"]["count"], 2)
            self.assertEqual(summary["by_node_kind"]["chunk"]["requests"] + summary["by_node_kind"]["reduce"]["requests"], summary["requests"])
            self.assertEqual(summary["prompts_over_the_monitors_input_limit"], 0)
            self.assertEqual(summary["units_chunked"], len(items))
            self.assertEqual(summary["monitor_reasoning_chars_per_request"]["max"], len("secret thoughts"))
            text = pilot.render(summary)
            self.assertIn("label-free", text)
            self.assertIn("invalid reasons", text)

    def test_prompts_over_the_input_limit_are_counted(self):
        with TempDir() as root:
            registry = make_project(root)
            run_dir = run(root, registry, spec_for(), FakeMonitor())
            path = run_dir / "items.jsonl"
            rows = lines(path)
            rows[0]["max_prompt_tokens"] = 99999
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            self.assertEqual(pilot.summarize(run_dir)["prompts_over_the_monitors_input_limit"], 1)

    def test_orphan_nodes_of_interrupted_units_are_ignored(self):
        with TempDir() as root:
            registry = make_project(root)
            run_dir = run(root, registry, spec_for(), FakeMonitor())
            path = run_dir / "items.jsonl"
            kept = path.read_text().splitlines()[:-2]
            path.write_text("\n".join(kept) + "\n")
            with_orphans = pilot.summarize(run_dir)
            self.assertEqual(with_orphans["units"], len(kept))
            live = {json.loads(l)["unit_id"] for l in kept}
            expected = sum(len(n["attempts"]) for n in lines(run_dir / "nodes.jsonl") if n["unit_id"] in live)
            self.assertEqual(with_orphans["requests"], expected)

    def test_the_module_cannot_see_labels(self):
        source = inspect.getsource(pilot)
        for forbidden in ("from .data", "import data", "labels()", "side_success", "rollout.json", "load_set", "detected", '"letter"'):
            self.assertNotIn(forbidden, source.replace("never opens a rollout file", ""), forbidden)
        summary_keys = json.dumps(pilot.summarize.__code__.co_names)
        self.assertNotIn("labels", summary_keys)


if __name__ == "__main__":
    unittest.main()
