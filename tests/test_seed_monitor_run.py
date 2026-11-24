"""Splitting an existing baseline preserves cached work and source provenance."""

import json
import unittest

from monitor_experiment.artifacts import lock
from monitor_experiment import spec
from junlin.seed_monitor_run import seed
from tests.support import TempDir, make_project
from tests.test_runner import FakeMonitor, run, lines


class SeedTests(unittest.TestCase):
    def test_imports_only_compatible_model_units_and_the_runner_reuses_them(self):
        with TempDir() as root:
            registry = make_project(root)
            def experiment(name):
                return spec.parse_spec({"name": "baseline", "monitor": name,
                    "rollout_sets": ["original_clean", "main_only_v1"],
                    "grid": {"scope": ["action"]}, "options": {"samples": 1}})
            first = experiment("qwen3-1.7b")
            source = run(root, registry, first, FakeMonitor())
            run(root, registry, experiment("qwen3-4b"), FakeMonitor())
            original = {name: (source / name).read_bytes() for name in ("items.jsonl", "nodes.jsonl", "manifest.json")}
            manifest = json.loads(original["manifest.json"])
            ids = {c["cell_id"] for c in manifest["cells"] if c["label"]["monitor"] == "qwen3-1.7b"}
            target = root / "runs/parallel/qwen3-1.7b/baseline"
            count = seed(source, target, "qwen3-1.7b", ids)
            self.assertEqual(count, 12)
            imported = json.loads((target / "manifest.json").read_text())
            self.assertEqual(set(imported["monitors"]), {"qwen3-1.7b"})
            self.assertTrue(all(c["label"]["monitor"] == "qwen3-1.7b" for c in imported["cells"]))
            self.assertEqual(len(imported["sessions"]), 1)
            self.assertTrue((target / "imported-baseline-manifest.json").is_file())
            monitor = FakeMonitor()
            run(root, registry, first, monitor, out=target.parent)
            self.assertFalse(monitor.calls)
            self.assertEqual(len(lines(target / "items.jsonl")), 12)
            self.assertEqual(seed(source, target, "qwen3-1.7b", ids), 0)
            self.assertEqual(original, {name: (source / name).read_bytes() for name in original})
            with lock(source / ".monitor-job.lock"):
                with self.assertRaisesRegex(RuntimeError, "still being written"):
                    seed(source, root / "another run", "qwen3-1.7b", ids)
            self.assertEqual(seed(source, root / "wrong revision", "qwen3-1.7b", {"wrong-cell-id"}), 0)


if __name__ == "__main__":
    unittest.main()
