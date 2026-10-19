"""Smoke checks on the cluster scripts: they cannot be run without Slurm and GPUs, but their syntax and safety properties can be."""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {name: ROOT / "mihai/cluster" / name for name in ("setup_cluster.sh", "run_controls.sbatch", "run_monitor.sbatch")}
WRITES = re.compile(r"(?:>>?\s*|\bmkdir(?:\s+-p)?\s+|\bln\s+-s\s+\S+\s+|\bcp\s+\S+\s+|\btee(?:\s+-a)?\s+|--out(?:put)?\s+|--cache-dir\s+)\"?\$SHARED")


class ScriptTests(unittest.TestCase):
    def test_every_script_parses_as_bash(self):
        for name, path in SCRIPTS.items():
            result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{name}: {result.stderr}")

    def test_scripts_fail_fast_and_are_executable(self):
        for name, path in SCRIPTS.items():
            text = path.read_text()
            self.assertIn("set -euo pipefail", text, name)
            self.assertTrue(path.stat().st_mode & 0o100, f"{name} is not executable")

    def test_nothing_is_ever_written_under_the_teammates_directory(self):
        for name, path in SCRIPTS.items():
            for number, line in enumerate(path.read_text().splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                self.assertIsNone(WRITES.search(line), f"{name}:{number} writes under $SHARED: {line.strip()}")

    def test_the_default_output_directory_is_the_users_own_not_the_teammates(self):
        for name, path in SCRIPTS.items():
            defaults = re.findall(r'ME="\$\{ME:-([^}]+)\}"', path.read_text())
            self.assertEqual(defaults, ["/nfs/roberts/project/cpsc4880/cpsc4880_as4833"], name)

    def test_the_control_job_protects_the_identity_of_the_cached_batch(self):
        text = SCRIPTS["run_controls.sbatch"].read_text()
        self.assertIn("verify-checkout", text)                   # same commit, unmodified, same implementation hash
        self.assertIn('EXPECTED_COMMIT="${EXPECTED_COMMIT:-5dc0417}"', text)
        self.assertIn("flock -n 9", text)                          # one pipeline at a time
        self.assertIn("--variants main_only", text)
        self.assertIn("--max-model-len \"$MAX_MODEL_LEN\" --yarn-factor \"$YARN_FACTOR\"", text)
        self.assertIn("MAX_MODEL_LEN=131072", text)
        self.assertIn("--tensor-parallel-size 1", text)
        self.assertIn("trap cleanup EXIT", text)
        self.assertNotIn("share_outputs", text, "the original's permission changes for teammates are not wanted here")

    def test_the_monitor_job_runs_one_monitor_and_scores_and_records_the_gpu(self):
        text = SCRIPTS["run_monitor.sbatch"].read_text()
        for needle in ("--monitor \"$MONITOR\"", "--base-url", "--gpu \"$GPU_LABEL\"", "--job-id \"$JOB\"", "--score", "serve_monitor.py",
                       ': "${MONITOR:?', "trap cleanup EXIT"):
            self.assertIn(needle, text)

    def test_setup_keeps_the_checkout_clean_and_verifies_it(self):
        text = SCRIPTS["setup_cluster.sh"].read_text()
        self.assertIn("verify-checkout", text)
        self.assertIn('ln -s "$ME/$name" "$CHECKOUT/$name"', text)
        self.assertIn("models cache", text)                        # only these git-ignored links are added to the checkout


if __name__ == "__main__":
    unittest.main()
