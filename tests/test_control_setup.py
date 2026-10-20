"""Preparation of the control run: model directory, derived config, checkout identity, worker plan."""

import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from monitor_experiment import control_setup as cs
from monitor_experiment.artifacts import read_json
from tests.support import TempDir

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "rollouts_original_clean/manifest.json"


def shared_model(directory):
    directory.mkdir(parents=True)
    (directory / "model-1.safetensors").write_bytes(b"x" * 10)
    (directory / "config.json").write_text("{}")
    (directory / "download-manifest.json").write_text(json.dumps(
        {"model_id": "Qwen/Qwen3-14B", "revision": "r", "files": {"model-1.safetensors": 10, "config.json": 2}}))
    return directory


class ModelDirTests(unittest.TestCase):
    def test_links_every_listed_file_and_copies_the_manifest_identically(self):
        with TempDir() as d:
            shared, private = shared_model(d / "shared"), d / "private"
            summary = cs.link_model_dir(shared, private)
            self.assertEqual((summary["files"], summary["bytes"], summary["revision"]), (2, 12, "r"))
            self.assertTrue((private / "model-1.safetensors").is_symlink())
            self.assertEqual((private / "model-1.safetensors").resolve(), (shared / "model-1.safetensors").resolve())
            self.assertEqual((private / "download-manifest.json").read_bytes(), (shared / "download-manifest.json").read_bytes())
            self.assertFalse((private / "download-manifest.json").is_symlink(), "the private manifest is a copy, so the shared one is never written")
            cs.link_model_dir(shared, private)       # idempotent

    def test_problems_with_the_shared_directory_are_reported_together(self):
        with TempDir() as d:
            shared = shared_model(d / "shared")
            (shared / "config.json").write_text("{}   ")
            (shared / "model-1.safetensors").unlink()
            with self.assertRaises(cs.SetupError) as raised:
                cs.link_model_dir(shared, d / "private")
            self.assertIn("model-1.safetensors: missing", str(raised.exception))
            self.assertIn("config.json: size", str(raised.exception))
            self.assertFalse((d / "private").exists(), "nothing is created when the source is bad")

    def test_a_conflicting_existing_file_is_refused(self):
        with TempDir() as d:
            shared, private = shared_model(d / "shared"), d / "private"
            private.mkdir()
            (private / "config.json").write_text("something else")
            with self.assertRaisesRegex(cs.SetupError, "already exists"):
                cs.link_model_dir(shared, private)


class ConfigTests(unittest.TestCase):
    def test_only_variants_and_samples_change_in_the_real_config(self):
        source = (ROOT / "mihai/configs/rollouts-output-32768.toml").read_text()
        derived = cs.derive_config(source, variants=["main_only"], samples=12)
        a, b = tomllib.loads(source), tomllib.loads(derived)
        self.assertEqual(b["tasks"]["variants"], ["main_only"])
        self.assertEqual(b["tasks"]["samples"], 12)
        for section in a:
            for key in a[section]:
                if (section, key) not in (("tasks", "variants"), ("tasks", "samples")):
                    self.assertEqual(a[section][key], b[section][key], (section, key))
        self.assertEqual(b["generation"]["max_tokens"], 32768)
        self.assertEqual(b["generation"]["timeout"], 4800)
        self.assertTrue(derived.startswith("# Derived for the control rollouts"))

    def test_an_unexpected_source_is_refused_instead_of_guessed(self):
        with self.assertRaisesRegex(cs.SetupError, "exactly once"):
            cs.derive_config("[tasks]\nvariants = []\n", variants=["main_only"], samples=3)
        with self.assertRaisesRegex(cs.SetupError, "exactly once"):
            cs.derive_config('variants = ["benign", "malicious"]\nsamples = 8\nsamples = 8\n', variants=["main_only"], samples=3)


class WorkerPlanTests(unittest.TestCase):
    def test_each_requested_sample_is_covered_exactly_once(self):
        tasks = ("a", "b", "c")
        plan = cs.worker_plan(tasks, 12, 6)
        self.assertEqual(len(plan), 6)
        self.assertEqual([p["worker"] for p in plan], list(range(6)))
        for task in tasks:
            covered = sorted(s for p in plan if p["task"] == task for s in range(p["start_sample"], p["start_sample"] + p["samples"]))
            self.assertEqual(covered, list(range(12)))

    def test_uneven_blocks_and_a_top_up_offset(self):
        plan = cs.worker_plan(("a",), 7, 3, first_sample=12)
        self.assertEqual([(p["start_sample"], p["samples"]) for p in plan], [(12, 3), (15, 3), (18, 1)])
        with self.assertRaises(cs.SetupError):
            cs.worker_plan(("a",), 0, 3)


def make_repo(path):
    run = lambda *a: subprocess.run(["git", *a], cwd=path, check=True, capture_output=True,
                                    env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                                         "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"})
    run("init", "-q")
    for name in ("scripts", "monitor_experiment", "vendor", "configs", "prompts"):
        (path / name).mkdir()
        (path / name / "f.py").write_text(f"# {name}\n")
    (path / "requirements.txt").write_text("x\n")
    run("add", "-A")
    run("commit", "-q", "-m", "init")
    return run


class CheckoutTests(unittest.TestCase):
    def test_a_clean_checkout_with_the_expected_hash_passes_and_changes_are_caught(self):
        with TempDir() as d:
            run = make_repo(d)
            state = cs.checkout_state(d)
            self.assertTrue(state["clean"])
            commit = state["commit"]
            self.assertEqual(cs.verify_checkout(d, commit[:7], state["implementation_hash"])["commit"], commit)
            with self.assertRaisesRegex(cs.SetupError, "expected abc1234"):
                cs.verify_checkout(d, "abc1234", state["implementation_hash"])
            with self.assertRaisesRegex(cs.SetupError, "implementation hash"):
                cs.verify_checkout(d, commit[:7], "0" * 64)
            (d / "monitor_experiment/f.py").write_text("# changed\n")
            with self.assertRaisesRegex(cs.SetupError, "differs from its commit"):
                cs.verify_checkout(d, commit[:7], state["implementation_hash"])

    def test_untracked_data_directories_do_not_make_a_checkout_dirty(self):
        with TempDir() as d:
            make_repo(d)
            (d / "cache").mkdir()
            (d / "cache" / "x").write_text("data")
            (d / "models").symlink_to(d / "cache")
            self.assertTrue(cs.checkout_state(d)["clean"])

    @unittest.skipUnless(ORIGINAL.is_file(), "the cached batch is not present locally")
    def test_commit_5dc0417_reproduces_the_cached_batchs_implementation_hash(self):
        """The decisive check for 'generate the controls from the pristine commit' (needs the repository's git history)."""
        probe = subprocess.run(["git", "rev-parse", "--verify", "5dc0417^{commit}"], cwd=ROOT, capture_output=True, text=True)
        if probe.returncode:
            self.skipTest("commit 5dc0417 is not in this clone")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "monitor_experiment"
            folder.mkdir()
            names = subprocess.run(["git", "ls-tree", "--name-only", "5dc0417", "monitor_experiment/"], cwd=ROOT,
                                   capture_output=True, text=True).stdout.split()
            for name in names:
                if name.endswith(".py"):
                    (folder / Path(name).name).write_text(subprocess.run(["git", "show", f"5dc0417:{name}"], cwd=ROOT,
                                                                         capture_output=True, text=True).stdout)
            self.assertEqual(cs.implementation_hash(d), read_json(ORIGINAL)["runtime_implementation_hash"])

    def test_the_current_branch_does_not_reproduce_it_so_controls_cannot_come_from_here(self):
        if not ORIGINAL.is_file():
            self.skipTest("the cached batch is not present locally")
        self.assertNotEqual(cs.implementation_hash(ROOT), read_json(ORIGINAL)["runtime_implementation_hash"])


if __name__ == "__main__":
    unittest.main()
