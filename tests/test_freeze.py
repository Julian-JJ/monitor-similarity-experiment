"""Cell fingerprints, the freeze lock and the separate presence-rules lock."""

import json
import unittest
from pathlib import Path

from monitor_experiment import freeze
from monitor_experiment import spec as sp
from monitor_experiment.artifacts import read_json
from monitor_experiment.registry import Registry
from tests.support import TempDir, make_project

ROOT = Path(__file__).resolve().parents[1]


class FingerprintTests(unittest.TestCase):
    def test_cell_fingerprints_cover_only_what_shapes_a_monitors_input(self):
        prints = freeze.fingerprints(ROOT)
        self.assertEqual(set(prints["files"]), set(freeze.PROMPT_FILES))
        self.assertEqual(set(prints) - {"files", "tokenizer"}, set(freeze.EXTRA_FINGERPRINTS))
        for must in ("prompts/monitor_plan.txt", "prompts/monitor_reduce.txt", "prompts/monitor_chunk_notice.txt",
                     "prompts/monitor_plan_section.txt", "vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml"):
            self.assertIn(must, prints["files"])
        for must_not in ("configs/councils.toml", "configs/comparisons.toml", "configs/presence_rules.json"):
            self.assertNotIn(must_not, prints["files"], f"{must_not} only affects how results are read")

    def test_the_lock_covers_the_prompts_and_the_analysis_definitions_but_not_the_presence_rules(self):
        locked = freeze.lock_fingerprints(ROOT)["files"]
        self.assertEqual(set(locked), set(freeze.LOCKED_FILES))
        self.assertIn("configs/councils.toml", locked)
        self.assertIn("configs/comparisons.toml", locked)
        self.assertNotIn(freeze.RULES_FILE, locked)

    def test_editing_an_analysis_file_changes_the_lock_but_not_a_single_cell_id(self):
        with TempDir() as root:
            registry = make_project(root)
            raw = {"name": "t", "monitor": "qwen3-14b", "rollout_sets": ["original_clean"], "grid": {"scope": ["cot", "all"]}}
            before = [c.cell_id for c in sp.expand(sp.parse_spec(raw), registry, freeze.fingerprints(root))]
            freeze.write_lock("frozen", root)
            for relative in ("configs/councils.toml", "configs/comparisons.toml"):
                path = Path(root) / relative
                path.write_text(path.read_text() + "\n# an edit\n")
            after = [c.cell_id for c in sp.expand(sp.parse_spec(raw), registry, freeze.fingerprints(root))]
            self.assertEqual(before, after, "monitor results stay valid when only analysis definitions change")
            status, problems = freeze.check(root)
            self.assertEqual(status, "frozen")
            self.assertEqual(sorted(problems), ["configs/comparisons.toml differs from the lock", "configs/councils.toml differs from the lock"])
            with self.assertRaisesRegex(RuntimeError, "councils.toml"):
                freeze.require_ready(root)

    def test_editing_a_prompt_changes_every_cell_id(self):
        with TempDir() as root:
            registry = make_project(root)
            raw = {"name": "t", "monitor": "qwen3-14b", "rollout_sets": ["original_clean"], "grid": {"scope": ["cot", "all"]}}
            before = [c.cell_id for c in sp.expand(sp.parse_spec(raw), registry, freeze.fingerprints(root))]
            (Path(root) / "prompts/monitor_reduce.txt").write_text("changed")
            after = [c.cell_id for c in sp.expand(sp.parse_spec(raw), registry, freeze.fingerprints(root))]
            self.assertTrue(all(a != b for a, b in zip(before, after)))


class LockTests(unittest.TestCase):
    def test_missing_draft_and_frozen_behave_differently(self):
        with TempDir() as root:
            make_project(root)
            self.assertEqual(freeze.check(root)[0], "missing")
            self.assertEqual(freeze.require_ready(root)[0], "missing")         # a missing lock does not block
            freeze.write_lock("draft", root)
            self.assertEqual(freeze.check(root), ("draft", []))
            (Path(root) / "prompts/monitor_plan.txt").write_text("edited")
            self.assertEqual(freeze.check(root), ("draft", ["prompts/monitor_plan.txt differs from the lock"]))
            self.assertEqual(freeze.require_ready(root)[0], "draft")            # draft only warns
            freeze.write_lock("frozen", root)
            self.assertEqual(freeze.require_ready(root), ("frozen", []))
            (Path(root) / "prompts/monitor_reduce.txt").write_text("edited after freeze")
            with self.assertRaisesRegex(RuntimeError, "monitor_reduce.txt"):
                freeze.require_ready(root)

    def test_every_kind_of_change_is_detected_and_reverting_clears_it(self):
        with TempDir() as root:
            make_project(root)
            freeze.write_lock("frozen", root)
            for relative in ("configs/tool_lists.json", "configs/objectives.json", "configs/councils.toml"):
                path = Path(root) / relative
                original = path.read_text()
                path.write_text(original + " ")
                self.assertTrue(freeze.check(root)[1], relative)
                path.write_text(original)
                self.assertEqual(freeze.check(root)[1], [], f"restoring {relative} clears the problem")
            tokenizer = Path(root) / "cache/tokenizer/tokenizer.json"
            tokenizer.parent.mkdir(parents=True)
            tokenizer.write_text("{}")
            self.assertIn("tokenizer differs from the lock", freeze.check(root)[1])

    def test_a_file_added_to_the_lock_set_later_is_noticed(self):
        with TempDir() as root:
            make_project(root)
            freeze.write_lock("draft", root)
            lock_path = Path(root) / freeze.LOCK
            lock = json.loads(lock_path.read_text())
            del lock["fingerprints"]["files"]["configs/comparisons.toml"]
            lock_path.write_text(json.dumps(lock))
            self.assertIn("configs/comparisons.toml is locked now but was not when the lock was written", freeze.check(root)[1])

    def test_bad_status_is_rejected(self):
        with TempDir() as root:
            make_project(root)
            for write in (freeze.write_lock, freeze.write_rules_lock):
                with self.assertRaises(ValueError):
                    write("maybe", root)

    def test_the_committed_lock_is_consistent_if_frozen(self):
        lock = read_json(ROOT / freeze.LOCK)
        self.assertIn(lock["status"], ("draft", "frozen"))
        status, problems = freeze.check(ROOT)
        if status == "frozen":
            self.assertEqual(problems, [], "a frozen file changed: that is an amendment (docs/plan/07)")


class RulesLockTests(unittest.TestCase):
    def project_with_rules(self, root):
        make_project(root)
        (Path(root) / "configs").mkdir(exist_ok=True)
        (Path(root) / freeze.RULES_FILE).write_text(json.dumps({"version": "0.2", "rules": {}}))

    def test_the_rules_have_their_own_lock_and_do_not_touch_the_prompt_lock(self):
        with TempDir() as root:
            self.project_with_rules(root)
            self.assertEqual(freeze.rules_status(root)[0], "missing")
            data = freeze.write_rules_lock("draft", root)
            self.assertEqual((data["rules_version"], len(data["sha256"])), ("0.2", 64))
            freeze.write_lock("frozen", root)
            (Path(root) / freeze.RULES_FILE).write_text(json.dumps({"version": "0.3", "rules": {}}))
            self.assertEqual(freeze.check(root), ("frozen", []), "revising the rules does not violate the prompt freeze")
            status, problems = freeze.rules_status(root)
            self.assertEqual(status, "draft")
            self.assertIn("differs from its lock (version 0.2)", problems[0])
            freeze.write_rules_lock("frozen", root)
            self.assertEqual(freeze.rules_status(root), ("frozen", []))
            (Path(root) / freeze.RULES_FILE).write_text(json.dumps({"version": "0.4", "rules": {}}))
            self.assertEqual(freeze.rules_status(root)[0], "frozen")
            self.assertTrue(freeze.rules_status(root)[1])


if __name__ == "__main__":
    unittest.main()
