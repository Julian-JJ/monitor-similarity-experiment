"""Cluster setup and health checks without package installation, network, Slurm or GPUs."""

import argparse
from contextlib import redirect_stdout, redirect_stderr
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock

from junlin import setup_cluster_env as setup
from monitor_experiment import freeze
from tests.support import TempDir, make_project


class SetupTests(unittest.TestCase):
    def fixture(self, directory):
        root, project, shared = directory / "checkout", directory / "my project", directory / "shared"
        root.mkdir()
        registry = make_project(root)
        tokenizer = registry.reference_tokenizer
        tokenizer.parent.mkdir(parents=True)
        tokenizer.write_text("{}")
        freeze.write_lock("frozen", root)
        args = argparse.Namespace(project_dir=project, shared_dir=shared)
        values = setup.settings(root, args, {})
        return root, registry, values

    def test_account_defaults_and_existing_interpreter_overrides(self):
        args = argparse.Namespace(project_dir=None, shared_dir=None)
        values = setup.settings(Path("/tmp/checkout"), args, {"USER": "cpsc4880_jjj49"})
        self.assertEqual(values["ME"], "/nfs/roberts/project/cpsc4880/cpsc4880_jjj49")
        self.assertEqual(values["SERVING_PY"], values["GEMMA_SERVING_PY"])
        values = setup.settings(Path("/nfs/roberts/project/cpsc4880/cpsc4880_jjj49/repo"), args,
                                {"USER": "alias", "GEMMA_SERVING_PY": "/custom/bin/python"})
        self.assertTrue(values["ME"].endswith("cpsc4880_jjj49"))
        self.assertEqual(values["GEMMA_SERVING_PY"], "/custom/bin/python")

    def test_saved_defaults_survive_new_shells_without_executing_path_contents(self):
        with TempDir() as directory:
            path = directory / ".env.cluster"
            tricky = str(directory / "space ' $(touch SHOULD_NOT_EXIST)")
            setup.save_settings(path, {"ME": tricky, "ANALYSIS_PY": tricky + "/bin/python"})
            command = ['bash', '-c', 'source "$1"; printf "%s\\n" "$ME" "$ANALYSIS_PY"', 'bash', str(path)]
            result = subprocess.run(command, env={"PATH": os.environ["PATH"]}, text=True, capture_output=True, cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [tricky, tricky + "/bin/python"])
            result = subprocess.run(command, env={"PATH": os.environ["PATH"], "ME": "override"}, text=True, capture_output=True)
            self.assertEqual(result.stdout.splitlines()[0], "override")
            self.assertFalse((directory / "SHOULD_NOT_EXIST").exists())

    def test_shared_environments_are_never_installed_into(self):
        with TempDir() as directory:
            _, _, values = self.fixture(directory)
            values["GEMMA_SERVING_PY"] = str(directory / "shared/env/bin/python")
            runner = Mock()
            with self.assertRaisesRegex(setup.SetupError, "outside your project"):
                setup.install(values, runner)
            runner.assert_not_called()

    def test_installer_targets_private_environments_and_explicit_indexes(self):
        with TempDir() as directory:
            _, _, values = self.fixture(directory)
            commands = []
            setup.install(values, lambda command: commands.append([str(p) for p in command]))
            vllm = next(c for c in commands if "vllm" in c)
            self.assertIn(values["GEMMA_SERVING_PY"], vllm)
            self.assertEqual(vllm[vllm.index("--default-index") + 1], "https://pypi.org/simple")
            self.assertIn("unsafe-best-match", vllm)
            self.assertIn([values["ANALYSIS_PY"], "-m", "pip", "check"], commands)
            self.assertTrue(any(c[-4:] == ["pip", "check", "--python", values["GEMMA_SERVING_PY"]] for c in commands))
            self.assertFalse(any("download_monitor.py" in str(c) or "sbatch" in c for c in commands))

    def test_collection_links_and_broken_link_repair_preserve_source_data(self):
        with TempDir() as directory:
            root, registry, _ = self.fixture(directory)
            entry = registry.sets["original_clean"]
            source = directory / "original elsewhere"
            entry.root.rename(source)
            entry.root.symlink_to(directory / "missing old target")
            before = (source / "manifest.json").read_bytes()
            setup.connect_collection(entry, source, [])
            self.assertEqual(entry.root.resolve(), source)
            self.assertEqual((source / "manifest.json").read_bytes(), before)
            with self.assertRaisesRegex(setup.SetupError, "already points elsewhere"):
                setup.connect_collection(entry, registry.sets["main_only_v1"].root, [])

    def test_check_never_creates_a_missing_collection_link(self):
        with TempDir() as directory:
            _, registry, _ = self.fixture(directory)
            entry = registry.sets["original_clean"]
            source = directory / "collection"
            entry.root.rename(source)
            with self.assertRaisesRegex(setup.SetupError, "Missing original_clean"):
                setup.connect_collection(entry, source, [], check=True)
            self.assertFalse(entry.root.exists())

    def test_tokenizer_copy_verifies_hash_and_does_not_write_through_broken_link(self):
        with TempDir() as directory:
            root, registry, values = self.fixture(directory)
            destination = registry.reference_tokenizer
            destination.unlink()
            missing = directory / "must not create tokenizer.json"
            destination.symlink_to(missing)
            source = Path(values["SHARED"]) / "models/qwen3-14b/tokenizer.json"
            source.parent.mkdir(parents=True)
            source.write_text("wrong")
            with self.assertRaisesRegex(setup.SetupError, "checksum"):
                setup.prepare_tokenizer(registry, root, values, install_missing=True)
            self.assertTrue(destination.is_symlink())
            source.write_text("{}")
            setup.prepare_tokenizer(registry, root, values, install_missing=True)
            self.assertEqual(destination.read_text(), "{}")
            self.assertFalse(destination.is_symlink())
            self.assertFalse(missing.exists())

    def test_read_only_check_and_failure_do_not_save_success_configuration(self):
        with TempDir() as directory:
            root, _, values = self.fixture(directory)
            arguments = ["--project-dir", values["ME"], "--shared-dir", values["SHARED"]]
            with patch.object(setup, "ROOT", root), patch.object(setup, "verify", return_value={}), \
                 patch.object(setup, "install") as install, redirect_stdout(io.StringIO()):
                self.assertEqual(setup.main(["--check", *arguments]), 0)
                install.assert_not_called()
                self.assertFalse((root / ".env.cluster").exists())
                self.assertFalse(Path(values["ME"]).exists())
            with patch.object(setup, "ROOT", root), patch.object(setup, "verify", side_effect=setup.SetupError("bad vllm")), \
                 redirect_stderr(io.StringIO()):
                self.assertEqual(setup.main(arguments), 1)
                self.assertFalse((root / ".env.cluster").exists())

    def test_static_serving_checks_reject_old_gemma_support_without_loading_torch(self):
        with TempDir() as directory:
            for package in ("vllm", "torch", "transformers"):
                metadata = directory / f"{package}-0.0.0.dist-info"
                metadata.mkdir()
                (metadata / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {package}\nVersion: 0.0.0\n")
            model = directory / "vllm/model_executor/models/registry.py"
            reasoning = directory / "vllm/reasoning/__init__.py"
            config = directory / "transformers/models/auto/configuration_auto.py"
            for path in (model, reasoning, config):
                path.parent.mkdir(parents=True, exist_ok=True)
            model.write_text("registry = {'Gemma3ForConditionalGeneration': None}")
            reasoning.write_text("parsers = {'gemma4': None}")
            config.write_text("configs = {'gemma4': None, 'gemma4_unified': None}")
            command = [sys.executable, "-S", "-c", setup.SERVING_CHECK, "gemma"]
            result = subprocess.run(command, env={**os.environ, "PYTHONPATH": str(directory)}, text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unified 12B", result.stderr)
            model.write_text("registry = {'Gemma4ForConditionalGeneration': None, 'Gemma4UnifiedForConditionalGeneration': None}")
            result = subprocess.run(command, env={**os.environ, "PYTHONPATH": str(directory)}, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["packages"]["vllm"], "0.0.0")

    def test_successful_setup_saves_environment_and_verification_report(self):
        with TempDir() as directory:
            root, _, values = self.fixture(directory)
            arguments = ["--install", "--project-dir", values["ME"], "--shared-dir", values["SHARED"]]
            with patch.object(setup, "ROOT", root), patch.object(setup, "verify", return_value={}), \
                 patch.object(setup, "install") as install, patch.dict(os.environ, {}, clear=True), \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(setup.main(arguments), 0)
                install.assert_called_once()
            self.assertTrue((root / ".env.cluster").is_file())
            report_path, = (Path(values["ME"]) / "logs").glob("cluster-env-*.json")
            report = json.loads(report_path.read_text())
            self.assertEqual(report["settings"]["ME"], values["ME"])
            self.assertEqual(report["settings"]["GEMMA_SERVING_PY"], values["GEMMA_SERVING_PY"])
            self.assertFalse(report["gpu_inference_tested"])
            self.assertFalse(Path(values["SHARED"]).exists())


class HealthTests(unittest.TestCase):
    def test_job_exit_zero_alone_is_not_healthy_and_invalid_or_unscored_results_are_flagged(self):
        with TempDir() as project:
            run_dir = project / "runs/baseline"
            run_dir.mkdir(parents=True)
            logs = project / "logs/qwen-gemma-20261114"
            logs.mkdir(parents=True)
            (logs / "submissions.tsv").write_text("stage\tmonitor\tjob_id\nmonitor\tqwen3-1.7b\t1\nmonitor\tqwen3-4b\t2\n")
            for name, job in (("qwen3-1.7b", "1"), ("qwen3-4b", "2")):
                (project / f"logs/monitor-{name}-{job}.status").write_text("exit_code=0\n")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(setup.batch_status(project)["qwen3-1.7b"]["state"], "INCOMPLETE")
            cells, scored, items = [], [], []
            for name in setup.MODELS[:2]:
                for scope in ("action", "cot", "all"):
                    ident = name + scope
                    label = {"monitor": name, "scope": scope}
                    cells.append({"cell_id": ident, "label": label})
                    scored.append({"cell_id": ident, "label": label, "complete": True, "units_found": 600, "units_expected": 600})
                    items += [{"unit_id": ident + str(i), "cell_id": ident, "status": "complete"} for i in range(600)]
            (run_dir / "manifest.json").write_text(json.dumps({"cells": cells}))
            (run_dir / "metrics.json").write_text(json.dumps({"cells": scored}))
            items_path = run_dir / "items.jsonl"
            items_path.write_text("".join(json.dumps(item) + "\n" for item in items))
            output = io.StringIO()
            with redirect_stdout(output):
                status = setup.batch_status(project)
            self.assertEqual(status["qwen3-1.7b"]["state"], "HEALTHY")
            self.assertEqual(status["qwen3-4b"]["state"], "HEALTHY")
            self.assertIn("Both Qwen jobs completed healthily", output.getvalue())
            items[0]["status"] = "invalid"
            items_path.write_text("".join(json.dumps(item) + "\n" for item in items))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(setup.batch_status(project)["qwen3-1.7b"]["state"], "DONE_INVALID")
            (project / "logs/monitor-qwen3-4b-2.status").write_text("exit_code=1\n")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(setup.batch_status(project)["qwen3-4b"]["state"], "FAILED")


if __name__ == "__main__":
    unittest.main()
