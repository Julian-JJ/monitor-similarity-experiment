"""The report generator on real scored output from the miniature project."""

import json
import tempfile
import unittest
from pathlib import Path

from monitor_experiment import compare as cmp, hierarchy as h, report, runner
from monitor_experiment.artifacts import write_json
from tests.support import TempDir, make_project
from tests.test_compare import BEHAVIORS, comparison_file, make_runs

ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.registry = make_project(cls.root)
        cls.runs = make_runs(cls.root, cls.registry)
        cls.run_dir = cls.runs[0].path
        runner.score_run(cls.run_dir, cls.registry, bootstrap_n=100)
        pairs = cmp.pairs_for(cls.runs, cls.registry)
        path = comparison_file(cls.root, '''
[[comparisons]]
id = "oracle vs always-A"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-4b" }
[[comparisons]]
id = "missing"
a = { monitor = "qwen3-14b" }
b = { monitor = "gpt-oss-120b" }
''')
        write_json(cls.root / "comparisons.json", cmp.run_comparisons(path, cls.runs, pairs, ROOT / "configs/councils.toml", n=100))
        cls.text = report.render([cls.run_dir / "metrics.json"], cls.root / "comparisons.json", "Test report")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sections_and_cells_are_present(self):
        for heading in ("# Test report", "## Caveats", "## Settings", "## Both told objectives pooled", "## Told the malicious objective",
                        "## Told the benign objective", "## Secondary: objective-specificity", "## Sample sizes", "## Cost and latency",
                        "## Pre-registered comparisons"):
            self.assertIn(heading, self.text)
        for monitor in BEHAVIORS:
            self.assertIn(monitor, self.text)
        self.assertIn("same_model", self.text)
        self.assertIn("same_family_smaller", self.text)

    def test_values_come_from_the_stored_metrics(self):
        metrics = json.loads((self.run_dir / "metrics.json").read_text())
        oracle = next(c for c in metrics["cells"] if c["label"]["monitor"] == "qwen3-14b")
        self.assertEqual(oracle["results"]["pooled"]["metrics"]["gmean2_clean"]["value"], 1.0)
        self.assertIn("1.000 [1.000, 1.000]", self.text)
        self.assertIn("| qwen3-14b · cot · context none | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |", self.text)

    def test_automatic_caveats(self):
        self.assertIn("**not frozen**", self.text)            # the miniature project has no lock
        self.assertIn("hierarchical monitor", self.text)      # chunked prompts in the test
        self.assertIn("held fixed in the bootstrap", self.text)
        self.assertIn("Cross-objective negatives", self.text)
        self.assertIn("Fewer than 30 positive pairs", self.text)

    def test_comparisons_include_skipped_ones_with_a_reason(self):
        self.assertIn("| oracle vs always-A | cot | A better | +1.000 |", self.text)
        self.assertIn("| missing | cot | skipped |", self.text)

    def test_missing_clean_negatives_are_called_out(self):
        with TempDir() as root:
            registry = make_project(root, controls=False)
            from monitor_experiment import spec as sp
            spec = sp.parse_spec({"name": "nc", "monitor": "qwen3-14b", "rollout_sets": ["original_clean"], "grid": {"scope": ["cot"]},
                                  "options": {"samples": 2, "chunk_tokens": 250, "single_pass_if_fits": False, "concurrency": 1}})
            run_dir = runner.run_experiment(spec, registry, Path(root) / "runs", make_complete=lambda m, r: (BEHAVIORS["qwen3-14b"], {}),
                                            count=lambda t: len(t.split()), prompts=h.load_prompts(), root=root, progress=lambda *_: None)
            runner.score_run(run_dir, registry, bootstrap_n=30)
            text = report.render([run_dir / "metrics.json"])
            self.assertIn("no clean negatives", text)
            self.assertIn("n/a", text)

    def test_formatting_helpers(self):
        self.assertEqual(report.fmt({"value": None}), "n/a")
        self.assertEqual(report.fmt({"value": 0.5}), "0.500")
        self.assertEqual(report.fmt({"value": 0.5, "low": 0.25, "high": 0.75}), "0.500 [0.250, 0.750]")


if __name__ == "__main__":
    unittest.main()
