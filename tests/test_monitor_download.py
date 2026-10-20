"""The monitor downloader and its verification, with the Hugging Face calls replaced."""

import json
import unittest
from pathlib import Path

from monitor_experiment import monitor_download as md
from monitor_experiment.registry import Registry
from tests.support import TempDir


def fake_fetch(files):
    def fetch(repo, revision, out, workers):
        for name, size in files.items():
            (Path(out) / name).write_bytes(b"x" * size)
    return fetch


GOOD = {"config.json": 10, "model-00001.safetensors": 100}


class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registered = Registry.load().monitor("qwen3-32b")
        cls.monitor = type(registered)(**{**registered.__dict__, "revision": md.UNPINNED})   # independent of the registry's current pin

    def run_download(self, out, files=GOOD, sha="a" * 40, **kw):
        return md.download(self.monitor, out, resolve=lambda repo, rev: sha, fetch=fake_fetch(files), **kw)

    def test_a_download_writes_the_manifest_last_and_removes_the_marker(self):
        with TempDir() as d:
            manifest = self.run_download(d / "m")
            self.assertEqual((manifest["model_id"], manifest["revision"]), ("Qwen/Qwen3-32B", "a" * 40))
            self.assertEqual(manifest["files"], GOOD)
            self.assertFalse((d / "m" / ".download-incomplete").exists())
            self.assertEqual(md.verify(d / "m", self.monitor)["revision"], "a" * 40)

    def test_a_failed_fetch_leaves_the_marker_and_no_manifest(self):
        def broken(*a):
            raise OSError("network")
        with TempDir() as d:
            with self.assertRaises(OSError):
                md.download(self.monitor, d / "m", resolve=lambda r, v: "b" * 40, fetch=broken)
            self.assertTrue((d / "m" / ".download-incomplete").exists())
            self.assertFalse((d / "m" / "download-manifest.json").exists())
            with self.assertRaises(md.DownloadError):
                md.verify(d / "m", self.monitor)

    def test_a_download_without_weights_is_refused_and_stays_marked_incomplete(self):
        with TempDir() as d:
            with self.assertRaisesRegex(md.DownloadError, "no safetensors"):
                self.run_download(d / "m", files={"config.json": 5})
            self.assertTrue((d / "m" / ".download-incomplete").exists())

    def test_verify_rejects_the_wrong_model_a_changed_file_and_a_wrong_revision(self):
        with TempDir() as d:
            self.run_download(d / "m")
            (d / "m" / "model-00001.safetensors").write_bytes(b"short")
            with self.assertRaisesRegex(md.DownloadError, "size differs"):
                md.verify(d / "m", self.monitor)
            (d / "m" / "model-00001.safetensors").write_bytes(b"x" * 100)
            other = Registry.load().monitor("qwen3-4b")
            with self.assertRaisesRegex(md.DownloadError, "holds Qwen/Qwen3-32B"):
                md.verify(d / "m", other)
            pinned = type(self.monitor)(**{**self.monitor.__dict__, "revision": "c" * 40})
            with self.assertRaisesRegex(md.DownloadError, "pins"):
                md.verify(d / "m", pinned)

    def test_a_pinned_registry_refuses_a_different_resolved_revision(self):
        pinned = type(self.monitor)(**{**self.monitor.__dict__, "revision": "c" * 40})
        with TempDir() as d:
            with self.assertRaisesRegex(md.DownloadError, "registry pins"):
                md.download(pinned, d / "m", resolve=lambda r, v: "d" * 40, fetch=fake_fetch(GOOD))
            self.assertFalse((d / "m").exists())

    def test_only_open_weights_cluster_monitors_can_be_downloaded(self):
        api_monitor = type(self.monitor)(**{**self.monitor.__dict__, "provider": "api"})
        with TempDir() as d:
            with self.assertRaisesRegex(md.DownloadError, "nothing to download"):
                md.download(api_monitor, d / "m", resolve=lambda r, v: "e" * 40, fetch=fake_fetch(GOOD))


if __name__ == "__main__":
    unittest.main()
