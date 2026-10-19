"""The per-pair driver, with a stub generator so no model is needed."""

import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

from monitor_experiment import collection_builder as cb
from monitor_experiment import control_setup as cs
from tests.support import TempDir

ROOT = Path(__file__).resolve().parents[1]

STUB = textwrap.dedent('''
    import sys, json, time
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    task, sample = args["--tasks"], int(args["--start-sample"])
    with open(args["--cache-dir"] + "/calls.jsonl", "a") as f:
        f.write(json.dumps({"task": task, "sample": sample, "samples": args["--samples"], "variant": args["--variants"], "t": time.time()}) + "\\n")
    time.sleep(0.2)
    sys.exit(1 if sample == 2 else 0)
''')


def fake_complete_entry(cache, task, sample, variant="main_only", status="complete"):
    (cache / "entries").mkdir(parents=True, exist_ok=True)
    (cache / "rollouts").mkdir(exist_ok=True)
    (cache / "followups").mkdir(exist_ok=True)
    rid = f"{task}{sample}{status}"
    (cache / "rollouts" / f"{rid}.json").write_text(json.dumps({"status": status}))
    (cache / "followups" / f"{rid}.json").write_text(json.dumps({"status": "complete"}))
    (cache / "entries" / f"{rid}.json").write_text(json.dumps({"task": task, "variant": variant, "sample": sample,
                                                                "rollout": f"rollouts/{rid}.json", "followups": [f"followups/{rid}.json"]}))


def run(d, extra=()):
    stub = d / "stub.py"
    stub.write_text(STUB)
    cache = d / "cache"
    cache.mkdir(exist_ok=True)
    return subprocess.run([sys.executable, str(ROOT / "scripts/run_pairs.py"), "--checkout", str(d), "--generator", str(stub),
                           "--config", "c.toml", "--base-url", "http://x/v1", "--cache-dir", str(cache), "--log-dir", str(d / "logs"),
                           "--samples", "4", "--parallel", "3", *extra], capture_output=True, text=True), cache


def calls(cache):
    return [json.loads(l) for l in (cache / "calls.jsonl").read_text().splitlines()]


class DriverTests(unittest.TestCase):
    def test_every_pair_runs_in_its_own_process_and_one_failure_does_not_stop_the_others(self):
        with TempDir() as d:
            result, cache = run(d)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            made = calls(cache)
            self.assertEqual(len(made), 12)                           # 3 tasks x 4 samples
            self.assertTrue(all(c["samples"] == "1" and c["variant"] == "main_only" for c in made))
            self.assertEqual(sorted((c["task"], c["sample"]) for c in made), sorted(cs.pair_list(("bank_transfer_2", "american_airlines_2", "spam_filter_update"), 4)))
            summary = json.loads((d / "logs/summary.json").read_text())
            self.assertEqual((summary["attempted"], summary["failed"]), (12, 3))   # sample 2 of each task failed; samples 3 still ran
            self.assertEqual({r["sample"] for r in summary["results"] if r["returncode"]}, {2})
            self.assertIn("FAIL bank_transfer_2 sample 2", result.stdout)
            self.assertTrue((d / "logs/bank_transfer_2-sample03.log").exists(), "each pair has its own log")

    def test_pairs_already_complete_in_the_cache_are_skipped_whatever_their_serving_identity(self):
        with TempDir() as d:
            cache = d / "cache"
            fake_complete_entry(cache, "bank_transfer_2", 0)
            fake_complete_entry(cache, "spam_filter_update", 3)
            fake_complete_entry(cache, "american_airlines_2", 1, status="error")       # not complete: must be rerun
            result, cache = run(d)
            made = {(c["task"], c["sample"]) for c in calls(cache)}
            self.assertNotIn(("bank_transfer_2", 0), made)
            self.assertNotIn(("spam_filter_update", 3), made)
            self.assertIn(("american_airlines_2", 1), made)
            self.assertEqual(len(made), 10)
            self.assertIn("2 already complete", result.stdout)

    def test_the_other_variant_does_not_count_as_complete(self):
        with TempDir() as d:
            fake_complete_entry(d / "cache", "bank_transfer_2", 0, variant="benign")
            result, cache = run(d)
            self.assertIn(("bank_transfer_2", 0), {(c["task"], c["sample"]) for c in calls(cache)})

    def test_pairs_are_started_interleaved_across_tasks_so_a_partial_run_is_balanced(self):
        order = cs.pair_list(("a", "b", "c"), 2, first_sample=5)
        self.assertEqual(order, [("a", 5), ("b", 5), ("c", 5), ("a", 6), ("b", 6), ("c", 6)])
        with self.assertRaises(cs.SetupError):
            cs.pair_list(("a",), 0)

    def test_it_is_a_failure_only_when_every_attempt_failed(self):
        with TempDir() as d:
            result, cache = run(d, ["--first-sample", "2", "--samples", "1"])    # only sample 2: every pair fails
            self.assertEqual(result.returncode, 1)
            self.assertIn("attempted 3, failed 3", result.stdout)

    def test_parallelism_is_bounded(self):
        with TempDir() as d:
            result, cache = run(d)
            stamps = sorted(c["t"] for c in calls(cache))
            # With 3 slots and 0.2 s per stub call, 12 calls cannot all start inside the first 0.2 s.
            self.assertGreater(stamps[-1] - stamps[0], 0.35)


class BuilderGuardTests(unittest.TestCase):
    def test_completed_samples_ignores_incomplete_ones(self):
        with TempDir() as d:
            fake_complete_entry(d, "bank_transfer_2", 0)
            fake_complete_entry(d, "bank_transfer_2", 1, status="error")
            self.assertEqual(cb.completed_samples(d, "main_only"), {("bank_transfer_2", 0)})

    def test_two_complete_entries_for_one_sample_are_refused_not_chosen_between(self):
        import tempfile
        from monitor_experiment.rollouts import generate
        from tests.test_collection_builder import CONFIG, FINISH
        from tests.test_rollouts import FakeClient
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache"
            generate(CONFIG, FakeClient(FINISH()), cache, ["bank_transfer_2"], ["main_only"], 1)
            other = {**CONFIG, "model": {**CONFIG["model"], "serving": {"served_model_name": "fake@2"}}}   # a second server
            generate(other, FakeClient(FINISH()), cache, ["bank_transfer_2"], ["main_only"], 1)
            with self.assertRaisesRegex(cb.CollectionError, "More than one entry"):
                cb.build_collection(cache, Path(d) / "out", name="c")


if __name__ == "__main__":
    unittest.main()
