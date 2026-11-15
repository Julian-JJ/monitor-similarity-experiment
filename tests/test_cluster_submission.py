"""Exercise submission and dependencies with a fake sbatch; no Slurm, network or GPU."""

import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from monitor_experiment import freeze, spec
from monitor_experiment.registry import Registry
from tests.support import TempDir, make_project

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "junlin/submit_qwen_gemma_baselines.sh"
MODELS = ("qwen3-1.7b", "qwen3-4b", "gemma4-e2b", "gemma4-e4b", "gemma4-12b", "gemma4-31b")


class SubmissionTests(unittest.TestCase):
    def environment(self, temporary):
        root = temporary / "checkout with spaces"
        root.mkdir()
        make_project(root)
        (root / "monitor_experiment").symlink_to(ROOT / "monitor_experiment", target_is_directory=True)
        (root / "configs/experiments").mkdir()
        for filename in ("qwen-gemma-baseline.toml", "cuda-debug-qwen3-1.7b.toml"):
            shutil.copy(ROOT / "configs/experiments" / filename, root / "configs/experiments")
        tokenizer = root / "cache/tokenizer/tokenizer.json"
        tokenizer.parent.mkdir(parents=True)
        tokenizer.write_text("{}")
        freeze.write_lock("frozen", root)
        binaries = temporary / "bin"
        binaries.mkdir()
        fake = binaries / "sbatch"
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ['CAPTURE'])
rows = path.read_text().splitlines() if path.exists() else []
fields = ('MONITOR', 'FRAMEWORK', 'OUT', 'MODEL_DIR', 'PIN_REGISTRY_DIR', 'REGISTRY_DIR',
          'SERVING_PY', 'ANALYSIS_PY', 'EXPERIMENT', 'GPU_LABEL', 'TP', 'SCORE', 'EXTRA_ARGS',
          'ENFORCE_EAGER', 'CUDA_LAUNCH_BLOCKING', 'PORT')
record = {'args': sys.argv[1:], 'env': {k: os.environ.get(k) for k in fields}}
with path.open('a') as stream:
    stream.write(json.dumps(record) + '\\n')
gpu_arg = next((a for a in sys.argv[1:] if a.startswith('--gpus=')), None)
if gpu_arg:
    gpu_count = int(gpu_arg.rsplit(':', 1)[1])
    cpu_count = int(next(a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--cpus-per-task=')))
    if cpu_count > 6 * gpu_count:
        print('At most 6 CPUs per GPU are allowed', file=sys.stderr)
        sys.exit(1)
if os.environ.get('FAIL_GPU_SUBMIT') and any(a.startswith('--gpus=') for a in sys.argv):
    sys.exit(1)
print(str(1000 + len(rows)) + ';test-cluster')
''')
        fake.chmod(0o755)
        gemma_python = binaries / "gemma python"
        gemma_python.symlink_to(sys.executable)
        packages = temporary / "serving packages"
        metadata = packages / "vllm-0.0.0.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text("Metadata-Version: 2.1\nName: vllm\nVersion: 0.0.0\n")
        return {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                "PYTHONPATH": str(packages) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                "ME": str(temporary / "my project"), "FRAMEWORK": str(root),
                "SUBMIT_PY": sys.executable, "ANALYSIS_PY": sys.executable,
                "SERVING_PY": sys.executable, "GEMMA_SERVING_PY": str(gemma_python),
                "CAPTURE": str(temporary / "submissions.jsonl"), "DEPENDENCY_JOB_ID": ""}

    def run_script(self, env, *arguments):
        return subprocess.run(["bash", str(SCRIPT), *arguments], env=env, text=True, capture_output=True)

    def test_default_dry_run_submits_nothing_and_excludes_the_completed_monitors(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            env["SERVING_PY"] = str(temporary / "missing qwen environment/bin/python")
            env["GEMMA_SERVING_PY"] = str(temporary / "missing gemma environment/bin/python")
            result = self.run_script(env, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr.count("DRY-RUN"), 12)
            for name in MODELS:
                self.assertIn(name + ": preparation=", result.stdout)
            for name in ("qwen3-14b", "qwen3-32b", "qwen3-30b-a3b"):
                self.assertNotIn("MONITOR=" + name + " ", result.stderr)
            self.assertFalse(Path(env["CAPTURE"]).exists())
            self.assertFalse(Path(env["ME"]).exists())

    def test_a_serving_python_without_vllm_prevents_all_submissions(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            isolated = temporary / "python without vllm"
            isolated.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' -I -S "$@"\n')
            isolated.chmod(0o755)
            for setting, name in (("SERVING_PY", "qwen3-4b"), ("GEMMA_SERVING_PY", "gemma4-e2b")):
                with self.subTest(setting=setting):
                    selected = {**env, setting: str(isolated)}
                    result = self.run_script(selected, "qwen3-4b", "gemma4-e2b")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(name, result.stderr)
                    self.assertIn(setting, result.stderr)
                    self.assertIn(str(isolated), result.stderr)
                    self.assertIn("vLLM is not installed", result.stderr)
                    self.assertFalse(Path(env["CAPTURE"]).exists())
                    self.assertFalse(Path(env["ME"]).exists())

    def test_saved_configuration_restores_defaults_after_a_fresh_login(self):
        from junlin.setup_cluster_env import save_settings
        with TempDir() as temporary:
            env = self.environment(temporary)
            root = Path(env["FRAMEWORK"])
            (root / "junlin").mkdir()
            script = root / "junlin" / SCRIPT.name
            shutil.copy(SCRIPT, script)
            save_settings(root / ".env.cluster", {key: env[key] for key in (
                "ME", "FRAMEWORK", "SUBMIT_PY", "ANALYSIS_PY", "SERVING_PY", "GEMMA_SERVING_PY")})
            clean = {key: value for key, value in env.items() if key not in (
                "ME", "FRAMEWORK", "SUBMIT_PY", "ANALYSIS_PY", "SERVING_PY", "GEMMA_SERVING_PY")}
            result = subprocess.run(["bash", str(script), "gemma4-e2b"], env=clean, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in Path(env["CAPTURE"]).read_text().splitlines()]
            self.assertEqual(records[1]["env"]["SERVING_PY"], env["GEMMA_SERVING_PY"])
            self.assertEqual(records[1]["env"]["FRAMEWORK"], str(root))

    def test_short_gemma_and_qwen_commands_select_only_the_requested_family(self):
        for family, names in (("gemma", MODELS[2:]), ("qwen", MODELS[:2])):
            with self.subTest(family=family), TempDir() as temporary:
                env = self.environment(temporary)
                result = subprocess.run(["bash", str(ROOT / "junlin/run.sh"), family, "--dry-run"],
                                        env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr.count("DRY-RUN"), 2 * len(names))
                self.assertEqual([line.split(":")[0] for line in result.stdout.splitlines()], list(names))

    def test_debug_job_uses_a_separate_run_and_single_gpu_with_synchronous_eager_execution(self):
        with TempDir() as temporary:
            env = {**self.environment(temporary), "GPU_TIME": "", "GPU_COUNT": "2", "PORT": ""}
            result = subprocess.run(["bash", str(ROOT / "junlin/run.sh"), "debug"],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            cpu, gpu = [json.loads(line) for line in Path(env["CAPTURE"]).read_text().splitlines()]
            self.assertEqual(gpu["env"]["MONITOR"], "qwen3-1.7b")
            self.assertEqual(gpu["env"]["ENFORCE_EAGER"], "1")
            self.assertEqual(gpu["env"]["CUDA_LAUNCH_BLOCKING"], "1")
            self.assertEqual(gpu["env"]["PORT"], "28475")
            self.assertEqual(gpu["env"]["SCORE"], "0")
            self.assertIn("--gpus=h200:1", gpu["args"])
            self.assertIn("--time=02:00:00", gpu["args"])
            self.assertIn("logs/cuda-debug-", gpu["env"]["REGISTRY_DIR"])
            self.assertEqual(cpu["env"]["PIN_REGISTRY_DIR"], gpu["env"]["REGISTRY_DIR"])
            debug_spec = spec.load_spec(gpu["env"]["EXPERIMENT"])
            self.assertNotEqual(debug_spec.name, "baseline")
            self.assertEqual(debug_spec.options["item_limit"], 1)
            self.assertEqual(debug_spec.options["samples"], 1)
            self.assertEqual(debug_spec.options["concurrency"], 1)
            self.assertEqual(tuple(debug_spec.axes["scope"]), ("action", "cot", "all"))
            self.assertFalse(list(Path(env["ME"]).glob("logs/qwen-gemma-*")))

    def test_full_eager_retry_is_opt_in(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            result = self.run_script(env, "--eager", "qwen3-1.7b")
            self.assertEqual(result.returncode, 0, result.stderr)
            _, gpu = [json.loads(line) for line in Path(env["CAPTURE"]).read_text().splitlines()]
            self.assertEqual(gpu["env"]["ENFORCE_EAGER"], "1")
            self.assertEqual(gpu["env"]["SCORE"], "1")
            self.assertEqual(spec.load_spec(gpu["env"]["EXPERIMENT"]).name, "baseline")

    def test_preparations_gate_each_gpu_and_gpu_jobs_are_serialized(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            env["DEPENDENCY_JOB_ID"] = "999"
            result = self.run_script(env, "qwen3-4b", "gemma4-e2b")
            self.assertEqual(result.returncode, 0, result.stderr)
            records = [json.loads(line) for line in Path(env["CAPTURE"]).read_text().splitlines()]
            self.assertEqual(len(records), 4)
            cpu1, gpu1, cpu2, gpu2 = records
            self.assertIn("--dependency=afterok:1000,afterany:999", gpu1["args"])
            self.assertIn("--dependency=afterok:1002,afterany:1001", gpu2["args"])
            self.assertIn("--kill-on-invalid-dep=yes", gpu2["args"])
            for cpu, gpu in ((cpu1, gpu1), (cpu2, gpu2)):
                self.assertIn("--partition=day", cpu["args"])
                self.assertIn("--cpus-per-task=4", cpu["args"])
                self.assertIn("--gpus=h200:1", gpu["args"])
                self.assertIn("--cpus-per-task=6", gpu["args"])
                self.assertIn("--time=08:00:00", gpu["args"])
                self.assertEqual(cpu["env"]["PIN_REGISTRY_DIR"], gpu["env"]["REGISTRY_DIR"])
                self.assertEqual(cpu["env"]["OUT"], gpu["env"]["MODEL_DIR"])
                self.assertEqual(gpu["env"]["SCORE"], "1")
                self.assertEqual(gpu["env"]["ENFORCE_EAGER"], "0")
                self.assertEqual(gpu["env"]["EXTRA_ARGS"], "")
            self.assertEqual(gpu1["env"]["SERVING_PY"], env["SERVING_PY"])
            self.assertEqual(gpu2["env"]["SERVING_PY"], env["GEMMA_SERVING_PY"])
            receipt = next(Path(env["ME"]).glob("logs/qwen-gemma-*/submissions.tsv"))
            with receipt.open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual([r["stage"] for r in rows], ["prepare", "monitor", "prepare", "monitor"])
            self.assertEqual([r["job_id"] for r in rows], ["1000", "1001", "1002", "1003"])

    def test_gpu_count_scales_the_allocation_and_tensor_parallelism(self):
        with TempDir() as temporary:
            env = {**self.environment(temporary), "GPU_COUNT": "2"}
            result = self.run_script(env, "gemma4-e2b")
            self.assertEqual(result.returncode, 0, result.stderr)
            cpu, gpu = [json.loads(line) for line in Path(env["CAPTURE"]).read_text().splitlines()]
            self.assertIn("--cpus-per-task=4", cpu["args"])
            self.assertIn("--gpus=h200:2", gpu["args"])
            self.assertIn("--cpus-per-task=12", gpu["args"])
            self.assertEqual(gpu["env"]["TP"], "2")
            self.assertEqual(gpu["env"]["GPU_LABEL"], "H200:2")

    def test_invalid_or_duplicate_selections_submit_nothing(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            for names in (("qwen3-4b", "typo"), ("qwen3-4b", "qwen3-4b"), ("qwen3-32b",)):
                result = self.run_script(env, *names)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(Path(env["CAPTURE"]).exists())

    def test_missing_rollouts_prevent_all_submissions(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            (Path(env["FRAMEWORK"]) / "coll_controls/manifest.json").unlink()
            result = self.run_script(env, "qwen3-4b")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing rollout collection", result.stderr)
            self.assertFalse(Path(env["CAPTURE"]).exists())

    def test_a_failed_gpu_submission_retains_the_preparation_receipt(self):
        with TempDir() as temporary:
            env = {**self.environment(temporary), "FAIL_GPU_SUBMIT": "1"}
            result = self.run_script(env, "qwen3-4b", "gemma4-e2b")
            self.assertNotEqual(result.returncode, 0)
            receipt = next(Path(env["ME"]).glob("logs/qwen-gemma-*/submissions.tsv"))
            with receipt.open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual([(r["stage"], r["job_id"]) for r in rows], [("prepare", "1000")])
            self.assertEqual(len(Path(env["CAPTURE"]).read_text().splitlines()), 2)

    def test_the_new_spec_preserves_the_baseline_cell_settings(self):
        registry = Registry.load()
        old = spec.parse_spec({"name": "baseline", "monitor": "qwen3-4b",
                               "rollout_sets": ["original_clean", "main_only_v1"],
                               "grid": {"scope": ["action", "cot", "all"]}, "options": {"samples": 4}})
        new = spec.load_spec(ROOT / "configs/experiments/qwen-gemma-baseline.toml")
        fingerprints = {"prompts": "same", "tokenizer": "same"}
        old_cells = spec.expand(old, registry, fingerprints)
        new_cells = [cell for cell in spec.expand(new, registry, fingerprints) if cell.monitor == "qwen3-4b"]
        self.assertEqual([cell.cell_id for cell in old_cells], [cell.cell_id for cell in new_cells])
        self.assertEqual(new.options["concurrency"], 32)


if __name__ == "__main__":
    unittest.main()
