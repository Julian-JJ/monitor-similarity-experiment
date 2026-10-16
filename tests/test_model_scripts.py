"""Exercise downloader/launcher control flow without network, weights, or GPUs."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from monitor_experiment.artifacts import digest, lock, read_json, write_json
from monitor_experiment.serving import make_manifest, validate_manifest

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
            self.assertNotIn(".model.lock", manifest["files"])
            with lock(Path(directory) / ".model.lock"), \
                 patch.dict(sys.modules, {"huggingface_hub": fake}), \
                 patch.object(sys, "argv", ["download_model.py", "--output-dir", directory]):
                with self.assertRaisesRegex(RuntimeError, "owns"):
                    module.main()
            self.assertEqual(len(calls), 1)
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
                 patch.object(module, "ROOT", Path(directory)), \
                 patch.object(module.socket, "create_server"), \
                 patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as execute:
                module.main()
            command = execute.call_args.args[0]
            self.assertIn("hermes", command)
            self.assertIn("qwen3", command)
            self.assertEqual(json.loads(command[command.index("--rope-scaling") + 1])["factor"], 2)
            manifest = read_json(Path(directory) / "serving-manifest.json")
            self.assertEqual(manifest["settings"]["revision"], "sha")
            self.assertEqual(command, manifest["command"])
            self.assertEqual(command[-2:], ["--served-model-name", manifest["served_model_name"]])
            self.assertEqual(len(execute.call_args.kwargs["pass_fds"]), 2)
            self.assertEqual(validate_manifest(manifest, read_json(Path(directory) / "download-manifest.json")),
                             manifest["served_model_name"])

    def test_second_server_and_occupied_port_do_not_replace_manifest(self):
        module = load("serve_model")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "download-manifest.json", {
                "model_id": "Qwen/Qwen3-14B", "revision": "sha", "files": {}})
            manifest_path = root / "serving-manifest.json"
            write_json(manifest_path, {"previous": "server"})
            original = manifest_path.read_bytes()
            with patch.object(module, "ROOT", root), \
                 patch.object(sys, "argv", ["serve_model.py", "--model-dir", directory]), \
                 patch.object(module.importlib.metadata, "version", return_value="test-version"), \
                 patch.object(module.subprocess, "run") as execute:
                for owned in (root / ".runtime/actor-server.lock", root / ".model.lock"):
                    with lock(owned):
                        with self.assertRaisesRegex(RuntimeError, "owns"):
                            module.main()
                    self.assertEqual(manifest_path.read_bytes(), original)
                with patch.object(module.socket, "create_server", side_effect=OSError("Address in use")):
                    with self.assertRaises(SystemExit):
                        module.main()
                self.assertEqual(manifest_path.read_bytes(), original)
                execute.assert_not_called()

    def test_failed_server_start_propagates_failure(self):
        module = load("serve_model")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "download-manifest.json", {
                "model_id": "Qwen/Qwen3-14B", "revision": "sha", "files": {}})
            with patch.object(module, "ROOT", root), \
                 patch.object(sys, "argv", ["serve_model.py", "--model-dir", directory]), \
                 patch.object(module.importlib.metadata, "version", return_value="test-version"), \
                 patch.object(module.socket, "create_server"), \
                 patch.object(module.subprocess, "run", return_value=types.SimpleNamespace(returncode=1)):
                with self.assertRaises(SystemExit) as caught:
                    module.main()
            self.assertEqual(caught.exception.code, 1)
            # Failure releases both locks so a corrected launch can proceed.
            with lock(root / ".runtime/actor-server.lock"), lock(root / ".model.lock"):
                pass

    def test_serving_configuration_is_bound_to_model_name(self):
        download = {"model_id": "Qwen/Qwen3-14B", "revision": "sha", "files": {}}
        settings = {"model_id": download["model_id"], "revision": "sha",
                    "download_manifest_hash": digest(download),
                    "command": ["python", "server", "--max-model-len", "32768"]}
        manifest = make_manifest(settings)
        self.assertEqual(manifest, make_manifest(settings))
        validate_manifest(manifest, download)
        changed = {**settings, "command": ["python", "server", "--max-model-len", "65536"]}
        self.assertNotEqual(make_manifest(changed)["served_model_name"], manifest["served_model_name"])
        manifest["settings"] = changed
        with self.assertRaisesRegex(ValueError, "disagree"):
            validate_manifest(manifest, download)
        with self.assertRaisesRegex(ValueError, "downloaded"):
            validate_manifest(make_manifest(settings), {**download, "revision": "different"})
        with self.assertRaisesRegex(ValueError, "Restart"):
            validate_manifest({"revision": "sha"}, download)

    def test_inherited_lock_survives_parent_descriptor_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.lock"
            child = None
            try:
                with lock(path) as descriptor:
                    child = subprocess.Popen(
                        [sys.executable, "-c", "import sys; print('ready', flush=True); sys.stdin.read()"],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, pass_fds=(descriptor,))
                    self.assertEqual(child.stdout.readline().strip(), "ready")
                with self.assertRaisesRegex(RuntimeError, "owns"):
                    with lock(path):
                        pass
            finally:
                if child is not None:
                    child.communicate(timeout=10)
            with lock(path):
                pass


if __name__ == "__main__":
    unittest.main()
