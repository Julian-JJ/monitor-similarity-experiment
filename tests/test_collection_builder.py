"""Build a collection from a real rollout cache (made by the real generator with a scripted client) and load it back."""

import json
import tempfile
import unittest
from pathlib import Path

from monitor_experiment import data
from monitor_experiment.artifacts import read_json
from monitor_experiment.collection_builder import CollectionError, build_collection
from monitor_experiment.rollouts import generate
from tests.test_rollouts import FakeClient, SETTINGS, response

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {"model": {"id": "test", "revision": "revision", "serving": {"served_model_name": "fake@1"}},
          "generation": {**SETTINGS, "seed": 42}, "followup": {"samples": 1, "max_tokens": 100}}
FINISH = lambda: [response("end_task"), response()]


def make_cache(folder):
    """Two complete main_only samples (bank 0, spam 0), one failed (bank 1), one never started (spam 1)."""
    generate(CONFIG, FakeClient(FINISH()), folder, ["bank_transfer_2"], ["main_only"], 1, start=0)
    generate(CONFIG, FakeClient(FINISH()), folder, ["spam_filter_update"], ["main_only"], 1, start=0)
    with_error = FakeClient([RuntimeError("server vanished")])
    try:
        generate(CONFIG, with_error, folder, ["bank_transfer_2"], ["main_only"], 1, start=1)
    except RuntimeError:
        pass


class BuilderTests(unittest.TestCase):
    def test_build_then_load_with_the_data_layer(self):
        with tempfile.TemporaryDirectory() as d:
            cache, out = Path(d) / "cache", Path(d) / "collection"
            make_cache(cache)
            manifest = build_collection(cache, out, name="main_only_v1", expect=2, source_job="42", hardware="H200 x1")
            self.assertEqual(manifest["counts"]["complete_pairs"], 2)
            self.assertEqual(manifest["counts"]["requested"], 4)
            reasons = {(e["task"], e["sample"]): e["reason"] for e in manifest["excluded"]}
            self.assertIn("actor error", reasons[("bank_transfer_2", 1)])
            self.assertIn("server vanished", reasons[("bank_transfer_2", 1)])
            self.assertEqual(reasons[("spam_filter_update", 1)], "never started")
            collection = data.RolloutSet.from_manifest("main_only_v1", out)       # verifies every checksum
            self.assertEqual(sorted(i.item_id for i in collection.items),
                             ["bank_transfer_2/main_only/sample_00", "spam_filter_update/main_only/sample_00"])
            item = collection.items[0]
            self.assertEqual((item.origin, item.variant, item.group), ("control", "main_only", "control/main_only/bank_transfer_2"))
            self.assertIsNone(item.embedded_objective())                         # controls have no side objective
            self.assertNotIn("system", {m["role"] for m in item.observation().messages})
            labels = item.labels()
            self.assertEqual((labels.malicious, labels.benign), (False, False))
            roles = {p.role for p in data.make_pairs(collection.items)}
            self.assertEqual(roles, {"clean_negative"})                          # nothing achieved: all clean negatives

    def test_files_are_byte_copies_and_checksums_are_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            cache, out = Path(d) / "cache", Path(d) / "collection"
            make_cache(cache)
            manifest = build_collection(cache, out, name="c")
            for pair in manifest["pairs"]:
                source = cache / next(read_json(p)["rollout"] for p in (cache / "entries").glob("*.json") if read_json(p)["rollout_id"] == pair["rollout_id"])
                self.assertEqual((out / pair["actor"]).read_bytes(), source.read_bytes())
                self.assertEqual(len(pair["actor_sha256"]), 64)
            self.assertEqual(manifest["model_revision"], "revision")
            self.assertEqual(manifest["generation"]["seed"], 42)
            self.assertEqual(len(manifest["runtime_implementation_hash"]), 64)

    def test_selection_ignores_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache"
            make_cache(cache)
            path = next((cache / "entries").glob("*.json"))
            entry = read_json(path)
            actor_path = cache / entry["rollout"]
            actor = read_json(actor_path)
            actor["evaluation"]["side"] = {"malicious": True, "benign": True}
            actor["evaluation"]["side_success"] = True
            actor_path.write_text(json.dumps(actor))
            manifest = build_collection(cache, Path(d) / "collection", name="c")
            self.assertEqual(manifest["counts"]["complete_pairs"], 2, "a rollout that achieved the objective is kept like any other")

    def test_refuses_to_overwrite_and_to_build_from_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            cache, out = Path(d) / "cache", Path(d) / "collection"
            make_cache(cache)
            build_collection(cache, out, name="c")
            with self.assertRaisesRegex(CollectionError, "already exists"):
                build_collection(cache, out, name="c")
            (Path(d) / "empty").mkdir()
            with self.assertRaisesRegex(CollectionError, "No complete"):
                build_collection(Path(d) / "empty", Path(d) / "out2", name="c")

    def test_a_follow_up_that_did_not_complete_excludes_the_sample(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache"
            make_cache(cache)
            entry = read_json(next(p for p in (cache / "entries").glob("*.json") if "bank" in read_json(p)["task"]))
            follow = cache / entry["followups"][0]
            record = read_json(follow)
            record["status"] = "error"
            follow.write_text(json.dumps(record))
            manifest = build_collection(cache, Path(d) / "collection", name="c")
            self.assertEqual(manifest["counts"]["complete_pairs"], 1)
            self.assertTrue(any("follow-up not complete" in e["reason"] for e in manifest["excluded"]))

    def test_disagreeing_generation_settings_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / "cache"
            make_cache(cache)
            path = next((cache / "entries").glob("*.json"))
            actor_path = cache / read_json(path)["rollout"]
            actor = read_json(actor_path)
            actor["identity"]["generation"]["temperature"] = 0.99
            actor_path.write_text(json.dumps(actor))
            with self.assertRaisesRegex(CollectionError, "disagree on their generation"):
                build_collection(cache, Path(d) / "collection", name="c")


if __name__ == "__main__":
    unittest.main()
