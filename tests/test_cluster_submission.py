"""Exercise submission and dependencies with a fake sbatch; no Slurm, network or GPU."""

import csv
import json
import os
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
        shutil.copy(ROOT / "configs/experiments/qwen-gemma-baseline.toml", root / "configs/experiments")
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
          'SERVING_PY', 'ANALYSIS_PY', 'EXPERIMENT', 'GPU_LABEL', 'TP', 'SCORE', 'EXTRA_ARGS')
record = {'args': sys.argv[1:], 'env': {k: os.environ.get(k) for k in fields}}
with path.open('a') as stream:
    stream.write(json.dumps(record) + '\\n')
if os.environ.get('FAIL_GPU_SUBMIT') and any(a.startswith('--gpus=') for a in sys.argv):
    sys.exit(1)
print(str(1000 + len(rows)) + ';test-cluster')
''')
        fake.chmod(0o755)
        gemma_python = binaries / "gemma python"
        gemma_python.symlink_to(sys.executable)
        return {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                "ME": str(temporary / "my project"), "FRAMEWORK": str(root),
                "SUBMIT_PY": sys.executable, "ANALYSIS_PY": sys.executable,
                "SERVING_PY": sys.executable, "GEMMA_SERVING_PY": str(gemma_python),
                "CAPTURE": str(temporary / "submissions.jsonl"), "DEPENDENCY_JOB_ID": ""}

    def run_script(self, env, *arguments):
        return subprocess.run(["bash", str(SCRIPT), *arguments], env=env, text=True, capture_output=True)

    def test_default_dry_run_submits_nothing_and_excludes_the_completed_monitors(self):
        with TempDir() as temporary:
            env = self.environment(temporary)
            result = self.run_script(env, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr.count("DRY-RUN"), 12)
            for name in MODELS:
                self.assertIn(name + ": preparation=", result.stdout)
            for name in ("qwen3-14b", "qwen3-32b", "qwen3-30b-a3b"):
                self.assertNotIn("MONITOR=" + name + " ", result.stderr)
            self.assertFalse(Path(env["CAPTURE"]).exists())
            self.assertFalse(Path(env["ME"]).exists())

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
                self.assertIn("--gpus=h200:1", gpu["args"])
                self.assertIn("--time=08:00:00", gpu["args"])
                self.assertEqual(cpu["env"]["PIN_REGISTRY_DIR"], gpu["env"]["REGISTRY_DIR"])
                self.assertEqual(cpu["env"]["OUT"], gpu["env"]["MODEL_DIR"])
                self.assertEqual(gpu["env"]["SCORE"], "1")
                self.assertEqual(gpu["env"]["EXTRA_ARGS"], "")
            self.assertEqual(gpu1["env"]["SERVING_PY"], env["SERVING_PY"])
            self.assertEqual(gpu2["env"]["SERVING_PY"], env["GEMMA_SERVING_PY"])
            receipt = next(Path(env["ME"]).glob("logs/qwen-gemma-*/submissions.tsv"))
            with receipt.open() as stream:
                rows = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual([r["stage"] for r in rows], ["prepare", "monitor", "prepare", "monitor"])
            self.assertEqual([r["job_id"] for r in rows], ["1000", "1001", "1002", "1003"])

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
