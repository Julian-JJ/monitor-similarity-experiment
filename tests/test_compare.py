"""Pre-registered comparisons and councils, on a miniature project with fake monitors of known behavior."""

import json
import tempfile
import unittest
from pathlib import Path

from monitor_experiment import compare as cmp
from monitor_experiment import hierarchy as h, runner
from monitor_experiment import spec as sp
from tests.support import TempDir, make_project

ROOT = Path(__file__).resolve().parents[1]
words = lambda text: len(text.split())


def reply(letter):
    return {"text": f"analysis <answer>{letter}</answer>", "finish_reason": "stop", "reasoning": None,
            "usage": {"prompt_tokens": 10, "completion_tokens": 3}, "latency_seconds": 0.2}


def is_plan(prompt):
    return prompt.startswith("You will be given a task that an AI agent")


def combining(prompt):
    """A combining prompt holds only chunk analyses: carry a chunk-level detection upward."""
    return "PARTIAL ANALYSIS" in prompt


def oracle(prompt, seed):
    """Detects exactly when the told objective is the one the rollout's agent pursued."""
    if is_plan(prompt):
        return {**reply("C"), "text": "PLAN: steps"}
    if combining(prompt):
        return reply("A" if "[partial verdict: A]" in prompt else "C")
    hit = ("send money to ACCT-9" in prompt and "TAGmalicious" in prompt) or ("split payments" in prompt and "TAGbenign" in prompt)
    return reply("A" if hit else "C")


def always_a(prompt, seed):
    return {**reply("C"), "text": "PLAN"} if is_plan(prompt) else reply("A")


def always_c(prompt, seed):
    return {**reply("C"), "text": "PLAN"} if is_plan(prompt) else reply("C")


def half(prompt, seed):
    """Detects only the malicious objective on malicious rollouts: recall 0.5, never a false alarm."""
    if is_plan(prompt):
        return {**reply("C"), "text": "PLAN"}
    if combining(prompt):
        return reply("A" if "[partial verdict: A]" in prompt else "C")
    return reply("A" if "send money to ACCT-9" in prompt and "TAGmalicious" in prompt else "C")


BEHAVIORS = {"qwen3-4b": always_a, "qwen3-14b": oracle, "qwen3-32b": always_c}


def make_runs(root, registry, behaviors=BEHAVIORS, samples=3, contexts=("none",)):
    spec = sp.parse_spec({"name": "r", "monitors": list(behaviors), "rollout_sets": ["original_clean", "main_only_v1"],
                          "grid": {"scope": ["cot"], "task_context": list(contexts)},
                          "options": {"samples": samples, "chunk_tokens": 250, "single_pass_if_fits": False, "concurrency": 2, "prep_samples": 2}})
    run_dir = runner.run_experiment(spec, registry, Path(root) / "runs", make_complete=lambda m, r: (behaviors[m.name], {}),
                                    count=words, prompts=h.load_prompts(), root=root, progress=lambda *_: None)
    return [cmp.Run(run_dir)]


def comparison_file(directory, body):
    path = Path(directory) / "comparisons.toml"
    path.write_text('metric = "gmean2_clean"\ntold = "pooled"\n' + body)
    return path


class SelectionTests(unittest.TestCase):
    def test_select_needs_exactly_one_match(self):
        with TempDir() as root:
            registry = make_project(root)
            runs = make_runs(root, registry)
            run, cell = cmp.select(runs, {"monitor": "qwen3-14b", "scope": "cot"})
            self.assertEqual(cell["label"]["monitor"], "qwen3-14b")
            with self.assertRaisesRegex(cmp.CompareError, "matches 3 cells"):
                cmp.select(runs, {"scope": "cot"})
            with self.assertRaisesRegex(cmp.CompareError, "matches 0 cells"):
                cmp.select(runs, {"monitor": "gpt-oss-120b"})


class ComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.registry = make_project(cls.root)
        cls.runs = make_runs(cls.root, cls.registry)
        cls.pairs = cmp.pairs_for(cls.runs, cls.registry)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def compare(self, body, **kwargs):
        path = comparison_file(self.root, body)
        return cmp.run_comparisons(path, self.runs, self.pairs, ROOT / "configs/councils.toml", n=200, **kwargs)

    def test_the_oracle_beats_the_trigger_happy_and_the_silent_monitor(self):
        out = self.compare('''
[[comparisons]]
id = "oracle vs always-A"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-4b" }
[[comparisons]]
id = "oracle vs always-C"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-32b" }
''')
        first, second = out["results"]
        self.assertEqual((first["primary"]["a"], first["primary"]["b"], first["primary"]["difference"]), (1.0, 0.0, 1.0))
        self.assertEqual((first["primary"]["low"], first["primary"]["high"]), (1.0, 1.0))
        self.assertEqual(first["outcome"], "A better")
        self.assertEqual(second["outcome"], "A better")
        self.assertEqual(second["recall"]["difference"], 1.0)
        self.assertEqual(first["family"], "cot")
        self.assertIsNotNone(first["p_holm"])
        self.assertGreaterEqual(first["p_holm"], first["primary"]["p_value"])

    def test_a_win_on_the_primary_metric_that_loses_on_recall_is_mixed(self):
        with TempDir() as root:
            registry = make_project(root)
            runs = make_runs(root, registry, {"qwen3-14b": half, "qwen3-4b": always_a})
            pairs = cmp.pairs_for(runs, registry)
            path = comparison_file(root, '''
[[comparisons]]
id = "half vs always-A"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-4b" }
''')
            result = cmp.run_comparisons(path, runs, pairs, ROOT / "configs/councils.toml", n=200)["results"][0]
            self.assertEqual((result["primary"]["a"], result["primary"]["b"]), (0.5, 0.0))   # g-mean2: 0.5*1 vs 1*0
            self.assertEqual((result["recall"]["a"], result["recall"]["b"]), (0.5, 1.0))
            self.assertEqual(result["outcome"], "mixed")

    def test_identical_monitors_show_no_clear_difference(self):
        out = self.compare('''
[[comparisons]]
id = "oracle vs itself"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-14b" }
''')
        self.assertEqual(out["results"][0]["outcome"], "no clear difference")
        self.assertEqual(out["results"][0]["primary"]["difference"], 0.0)

    def test_unavailable_cells_are_reported_as_skipped_not_dropped(self):
        out = self.compare('''
[[comparisons]]
id = "needs a monitor that was not run"
a = { monitor = "qwen3-14b" }
b = { monitor = "gpt-oss-120b" }
[[comparisons]]
id = "needs a plan cell"
a = { monitor = "qwen3-14b", task_context = "plan" }
b = { monitor = "qwen3-14b" }
''')
        self.assertTrue(all("skipped" in r and "matches 0 cells" in r["skipped"] for r in out["results"]), out["results"])

    def test_a_size_diverse_council_matches_its_best_member_when_the_best_member_is_the_majority_view(self):
        out = self.compare('''
[[comparisons]]
id = "P5a"
a = { monitor = "council:size-diverse" }
b = { monitor = "best_member_of:size-diverse" }
''')
        result = out["results"][0]
        # votes [always-A, oracle, always-C]: two of three agree with the oracle on every pair, so the council equals the oracle
        self.assertEqual((result["primary"]["a"], result["primary"]["b"]), (1.0, 1.0))
        self.assertEqual(result["outcome"], "no clear difference")
        self.assertEqual(result["b"]["monitor"], "best-member-of-size-diverse=qwen3-14b")

    def test_the_same_model_control_is_compared_as_one_majority_decision_per_pair(self):
        out = self.compare('''
[[comparisons]]
id = "size-diverse vs same-model control"
a = { monitor = "council:size-diverse" }
b = { monitor = "council:same-model-control" }
''')
        result = out["results"][0]
        self.assertEqual(result["note"], "sample counts differ: compared as one majority decision per pair")
        self.assertEqual(result["primary"]["a"], 1.0)   # the diverse council reproduces the oracle
        self.assertEqual(result["primary"]["b"], 0.0)   # three samples of the silent monitor never detect
        self.assertEqual(result["outcome"], "A better")

    def test_a_council_with_a_missing_member_is_skipped_with_a_reason(self):
        out = self.compare('''
[[comparisons]]
id = "family council"
a = { monitor = "council:family-diverse" }
b = { monitor = "qwen3-14b" }
''')
        self.assertIn("matches 0 cells", out["results"][0]["skipped"])

    def test_holm_is_applied_within_each_scope_separately(self):
        out = self.compare('''
[[comparisons]]
id = "c1"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-4b" }
[[comparisons]]
id = "c2"
a = { monitor = "qwen3-14b" }
b = { monitor = "qwen3-32b" }
''')
        ps = sorted(r["primary"]["p_value"] for r in out["results"])
        holm = sorted(r["p_holm"] for r in out["results"])
        self.assertAlmostEqual(holm[0], min(1.0, 2 * ps[0]))
        self.assertGreaterEqual(holm[1], holm[0])


if __name__ == "__main__":
    unittest.main()
