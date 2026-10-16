"""Exercise downloader/launcher control flow without network, weights, or GPUs."""

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor_experiment.artifacts import read_json, write_json

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModelScriptsTests(unittest.TestCase):
    def test_download_resolves_revision_and_commits_manifest_only_on_success(self):
        module = load("download_model")
        fake = types.ModuleType("huggingface_hub")
        fake.HfApi = lambda: types.SimpleNamespace(model_info=lambda *a, **k: types.SimpleNamespace(sha="immutable-sha"))
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            def snapshot(**kwargs):
                calls.append(kwargs)
                Path(directory, "config.json").write_text("{}")
                Path(directory, "model.safetensors").write_bytes(b"fake-test-weights")
            fake.snapshot_download = snapshot
            with patch.dict(sys.modules, {"huggingface_hub": fake}), \
                 patch("importlib.metadata.version", return_value="test-version"), \
                 patch.object(sys, "argv", ["download_model.py", "--output-dir", directory]):
                module.main()
            self.assertEqual(calls[0]["revision"], "immutable-sha")
            manifest = read_json(Path(directory) / "download-manifest.json")
            self.assertEqual(manifest["revision"], "immutable-sha")
            self.assertFalse(Path(directory, ".download-incomplete").exists())
            fake.snapshot_download = lambda **k: (_ for _ in ()).throw(RuntimeError("disconnect"))
            with patch.dict(sys.modules, {"huggingface_hub": fake}), \
                 patch("importlib.metadata.version", return_value="test-version"), \
                 patch.object(sys, "argv", ["download_model.py", "--output-dir", directory]):
                with self.assertRaisesRegex(RuntimeError, "disconnect"):
                    module.main()
            self.assertTrue(Path(directory, ".download-incomplete").exists())

    def test_launcher_records_parsers_scaling_and_revision_without_starting_gpu(self):
        module = load("serve_model")
        with tempfile.TemporaryDirectory() as directory:
            write_json(Path(directory) / "download-manifest.json", {
                "model_id": "Qwen/Qwen3-14B", "revision": "sha", "files": {}})
            with patch.object(sys, "argv", ["serve_model.py", "--model-dir", directory,
                                           "--max-model-len", "65536", "--yarn-factor", "2"]), \
                 patch.object(module.importlib.metadata, "version", return_value="test-version"), \
                 patch.object(module.os, "execv") as execute:
                module.main()
            command = execute.call_args.args[1]
            self.assertIn("hermes", command)
            self.assertIn("qwen3", command)
            self.assertEqual(json.loads(command[command.index("--rope-scaling") + 1])["factor"], 2)
            self.assertEqual(read_json(Path(directory) / "serving-manifest.json")["revision"], "sha")


if __name__ == "__main__":
    unittest.main()
