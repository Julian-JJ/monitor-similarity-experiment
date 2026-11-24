"""Reported-table preservation and read-only checks of realistic run artifacts."""

from dataclasses import replace
import json
from pathlib import Path
import unittest

from junlin import compile_results as cr
from monitor_experiment import runner, spec
from tests.support import TempDir, build_collection, make_project
from tests.test_runner import FakeMonitor, run

ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    def test_report_preserves_all_cells_and_does_not_claim_raw_verification(self):
        data = cr.read(ROOT / "junlin/results/reported-baseline.json")
        report = cr.render(data)
        self.assertEqual(len(data["cells"]), 24)
        self.assertEqual(len(data["source"]["sha256"]), 64)
        for cell in data["cells"]:
            for group in cell["groups"].values():
                self.assertEqual(set(group), set(cr.SCORES))
                for values in group.values():
                    self.assertIn(f"{values['value']:.3f} [{values['low']:.3f}, {values['high']:.3f}]", report)
        self.assertEqual(report, (ROOT / "junlin/results.md").read_text())
        self.assertEqual(report.count("| qwen3-14b | cot |"), 3)
        self.assertIn("raw cluster artifacts have not been verified", report)
        self.assertIn("0.859 / 0.127", report)
        self.assertFalse(data["source"]["raw_artifacts_verified"])
        with self.assertRaises(ValueError):
            cr.render({**data, "cells": data["cells"] + [data["cells"][0]]})


def fixture(root):
    registry = make_project(root, turns=2, words=3)
    cached = [("bank", "malicious" if s < 20 else "benign", s, s < 20, s >= 20) for s in range(41)]
    controls = [("bank", "main_only", s, False, False) for s in range(34)]
    for name, directory, rows in (("original_clean", "review_cached", cached),
                                   ("main_only_v1", "review_controls", controls)):
        path = build_collection(root / directory, rows, turns=2, words=3)
        registry.sets[name] = replace(registry.sets[name], root=path)
    experiment = spec.parse_spec({"name": "baseline", "monitor": "qwen3-14b",
        "rollout_sets": ["original_clean", "main_only_v1"],
        "grid": {"scope": ["action", "cot", "all"]}, "options": {"samples": 4}})
    directory = run(root, registry, experiment, FakeMonitor(), compute={"gpu_count": 1, "job_id": "42"})
    manifest = cr.read(directory / "manifest.json")
    identity = manifest["monitors"]["qwen3-14b"]
    manifest["served"]["qwen3-14b|default"]["served_model"] = identity["model_id"]
    (directory / "manifest.json").write_text(json.dumps(manifest))
    logs = root / "logs"
    logs.mkdir()
    (logs / "serving-qwen3-14b-42.json").write_text(json.dumps({"monitor_identity": identity, "vllm_version": "fixture"}))
    runner.score_run(directory, registry, bootstrap_n=5)
    return registry, directory, logs


class AuditTests(unittest.TestCase):
    def test_recomputes_saved_points_without_writing_and_accepts_invalid_answers(self):
        with TempDir() as root:
            registry, directory, logs = fixture(root)
            records = list(cr.jsonl(directory / "items.jsonl"))
            records[0].update(status="invalid", detected=None, letter=None)
            (directory / "items.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            runner.score_run(directory, registry, bootstrap_n=5)
            files = [p for p in directory.iterdir() if p.is_file()]
            before = {p: p.read_bytes() for p in files}
            audit = cr.audit_run(directory, "qwen3-14b", registry, logs)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(len(audit["cells"]), 3)
            self.assertEqual(audit["statuses"]["invalid"], 1)
            self.assertTrue(all(c["units_found"] == 600 for c in audit["cells"]))
            self.assertEqual(before, {p: p.read_bytes() for p in files})

    def test_detects_silent_identity_cache_and_duplicate_grid_errors(self):
        with TempDir() as root:
            registry, directory, logs = fixture(root)
            manifest = cr.read(directory / "manifest.json")
            manifest["served"]["qwen3-14b|default"]["served_model"] = "Qwen/Qwen3-4B"
            manifest["rollout_sets"]["original_clean"]["manifest_sha256"] = "old-content"
            (directory / "manifest.json").write_text(json.dumps(manifest))
            records = list(cr.jsonl(directory / "items.jsonl"))
            # Preserve record count but duplicate one key and remove another.
            records[1] = dict(records[0])
            (directory / "items.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            findings = "\n".join(cr.audit_run(directory, "qwen3-14b", registry, logs)["findings"])
            for text in ("Duplicate unit IDs", "collection hash differs", "Incomplete or duplicate unit grid", "Served-model"):
                self.assertIn(text, findings)

    def test_detects_stale_metrics_without_changing_them(self):
        with TempDir() as root:
            registry, directory, logs = fixture(root)
            path = directory / "metrics.json"
            scored = cr.read(path)
            scored["cells"][0]["results"]["pooled"]["metrics"]["tpr"]["value"] = 0.123
            path.write_text(json.dumps(scored))
            before = path.read_bytes()
            findings = "\n".join(cr.audit_run(directory, "qwen3-14b", registry, logs)["findings"])
            self.assertIn("Point estimate differs", findings)
            self.assertEqual(path.read_bytes(), before)

    def test_missing_sources_are_reported_without_claiming_success(self):
        with TempDir() as project:
            bundle = cr.export(project)
            self.assertFalse(bundle["raw_artifacts_verified"])
            self.assertEqual(len(bundle["runs"]), 8)
            self.assertTrue(all(r["findings"] for r in bundle["runs"]))


if __name__ == "__main__":
    unittest.main()
