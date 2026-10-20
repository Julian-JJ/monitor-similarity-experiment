"""Tool-list extraction from the vendored source, cross-checked against what the actor really called."""

import glob
import tempfile
import unittest
from pathlib import Path

from monitor_experiment import toollists as tl
from monitor_experiment.artifacts import read_json

ROOT = Path(__file__).resolve().parents[1]


class ExtractionTests(unittest.TestCase):
    def test_docstrings_and_names_from_a_synthetic_tree(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "tools").mkdir()
            (d / "environments").mkdir()
            (d / "tools/a.py").write_text('def send(x):\n    """Sends x.\n\n    More detail."""\n\ndef nodoc():\n    pass\n\ndef _private():\n    """hidden"""\n')
            (d / "environments/e.py").write_text("class E:\n    def post(self):\n        self.add_tools([send, nodoc, send])\n        other([ignored])\n")
            self.assertEqual(tl.function_docs(d / "tools"), {"send": "Sends x.", "nodoc": "", "_private": "hidden"})
            self.assertEqual(tl.tool_names(d / "environments/e.py"), ["end_task", "send", "nodoc", "send"])

    def test_a_tool_without_a_definition_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "tools").mkdir()
            (d / "environments").mkdir()
            (d / "tools/a.py").write_text('def end_task():\n    """Ends."""\n')
            for filename in tl.ENVIRONMENT_FILES.values():
                (d / "environments" / filename).write_text("class E:\n    def post(self):\n        self.add_tools([ghost])\n")
            with self.assertRaisesRegex(ValueError, "ghost"):
                tl.tool_lists(d)

    def test_formatting(self):
        self.assertEqual(tl.format_tools([{"name": "a", "description": "does a"}, {"name": "b", "description": ""}]),
                         "- a: does a\n- b")


class VendoredTests(unittest.TestCase):
    def test_committed_lists_match_a_fresh_extraction(self):
        committed = read_json(ROOT / "configs/tool_lists.json")["tools"]
        self.assertEqual(committed, tl.tool_lists())
        self.assertEqual({t: len(v) for t, v in committed.items()},
                         {"bank_transfer_2": 71, "american_airlines_2": 73, "spam_filter_update": 41})
        self.assertTrue(all(v[0]["name"] == "end_task" for v in committed.values()))

    @unittest.skipUnless(glob.glob(str(ROOT / "rollouts_original_clean/*/*/sample_*/rollout.json")), "no saved rollouts")
    def test_every_tool_the_actor_successfully_called_is_in_the_extracted_list(self):
        lists = {t: {e["name"] for e in v} for t, v in tl.tool_lists().items()}
        unlisted = {}
        for path in glob.glob(str(ROOT / "rollouts_original_clean/*/*/sample_*/rollout.json")):
            task = path.split("/")[-4]
            messages = read_json(path)["messages"]
            replies = {m["tool_call_id"]: m for m in messages if m["role"] == "tool"}
            for message in messages:
                for call in message.get("tool_calls") or []:
                    name = call["function"]["name"]
                    if name not in lists[task]:
                        unlisted[(task, name)] = str(replies[call["id"]]["content"])
        # The only calls outside the list must be inventions that the environment itself rejected.
        self.assertTrue(all(reply.startswith("ToolNotFoundError") for reply in unlisted.values()), unlisted)


if __name__ == "__main__":
    unittest.main()
