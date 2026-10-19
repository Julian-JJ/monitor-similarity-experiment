"""The freeze lock: fingerprints, draft versus frozen, and the committed lock."""

import json
import unittest
from pathlib import Path

from monitor_experiment import freeze
from monitor_experiment.artifacts import read_json
from tests.support import TempDir, make_project

ROOT = Path(__file__).resolve().parents[1]


class FreezeTests(unittest.TestCase):
    def test_fingerprints_cover_every_locked_file_and_the_extras(self):
        prints = freeze.fingerprints(ROOT)
        self.assertEqual(set(prints["files"]), set(freeze.LOCKED_FILES))
        self.assertTrue(all(len(h) == 64 for h in prints["files"].values()))
        self.assertEqual(set(prints) - {"files", "tokenizer"}, set(freeze.EXTRA_FINGERPRINTS))
        for must in ("prompts/monitor_plan.txt", "prompts/monitor_reduce.txt", "configs/presence_rules.json",
                     "vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml", "configs/councils.toml"):
            self.assertIn(must, prints["files"])

    def test_missing_lock_draft_and_frozen_behave_differently(self):
        with TempDir() as root:
            make_project(root)
            status, problems = freeze.check(root)
            self.assertEqual(status, "missing")
            self.assertEqual(freeze.require_ready(root)[0], "missing")         # a missing lock does not block
            freeze.write_lock("draft", root)
            self.assertEqual(freeze.check(root), ("draft", []))
            (Path(root) / "prompts/monitor_plan.txt").write_text("edited")
            status, problems = freeze.check(root)
            self.assertEqual(status, "draft")
            self.assertEqual(problems, ["prompts/monitor_plan.txt differs from the lock"])
            self.assertEqual(freeze.require_ready(root)[0], "draft")            # draft only warns
            freeze.write_lock("frozen", root)
            self.assertEqual(freeze.require_ready(root), ("frozen", []))
            (Path(root) / "prompts/monitor_reduce.txt").write_text("edited after freeze")
            with self.assertRaisesRegex(RuntimeError, "monitor_reduce.txt"):
                freeze.require_ready(root)

    def test_every_kind_of_change_is_detected(self):
        with TempDir() as root:
            make_project(root)
            freeze.write_lock("frozen", root)
            for relative in ("configs/tool_lists.json", "configs/objectives.json", "configs/councils.toml"):
                path = Path(root) / relative
                original = path.read_text()
                path.write_text(original + " ")
                status, problems = freeze.check(root)
                self.assertTrue(problems, relative)
                path.write_text(original)
                self.assertEqual(freeze.check(root)[1], [], f"restoring {relative} clears the problem")
            tokenizer = Path(root) / "cache/tokenizer/tokenizer.json"
            tokenizer.parent.mkdir(parents=True)
            tokenizer.write_text("{}")
            self.assertIn("tokenizer differs from the lock", freeze.check(root)[1])

    def test_bad_status_is_rejected(self):
        with TempDir() as root:
            make_project(root)
            with self.assertRaises(ValueError):
                freeze.write_lock("maybe", root)

    def test_the_committed_lock_exists_and_is_consistent_if_frozen(self):
        lock = read_json(ROOT / freeze.LOCK)
        self.assertIn(lock["status"], ("draft", "frozen"))
        status, problems = freeze.check(ROOT)
        if status == "frozen":
            self.assertEqual(problems, [], "a frozen file changed: that is an amendment (docs/plan/07)")


if __name__ == "__main__":
    unittest.main()
