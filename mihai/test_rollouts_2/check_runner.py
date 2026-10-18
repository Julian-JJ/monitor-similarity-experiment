#!/usr/bin/env python3
"""Offline failure-isolation and answer-leakage check; never invokes a model."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
import run
from runtime.serving import make_manifest
from runtime.artifacts import digest


def main():
    source = Path(__file__).resolve().parent
    sent = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        release, output, model = (root / x for x in ["release", "output", "model"])
        for path in [release, output, model]:
            path.mkdir()
        for name in ["config.json", "selection.json"]:
            (release / name).write_bytes((source / name).read_bytes())
        (release / "release-manifest.json").write_text('{}')
        download = {"model_id": "Qwen/Qwen3-14B", "revision": "test", "files": {}}
        (model / "download-manifest.json").write_text(json.dumps(download))
        serving = make_manifest({"model_id": download["model_id"], "revision": "test",
            "download_manifest_hash": digest(download), "command": ["fake"]})
        (output / "serving-manifest.json").write_text(json.dumps(serving))

        def fake_complete(self, messages, tools, settings, seed):
            assert tools == [] and seed == 42
            assert all(set(m) == {"role", "content"} for m in messages)
            sent.append(digest(messages))
            if messages == json.loads((release / 'selection.json').read_text())['cases'][0]['messages']:
                raise RuntimeError("Simulated individual failure")
            message = {"finish_reason": "stop", "reasoning": "test", "content": "Final answer: 24", "tool_calls": []}
            return message, {"usage": {"prompt_tokens": 1, "completion_tokens": 2}}

        args = ['run.py', '--release', str(release), '--output', str(output), '--model-dir', str(model), '--job-id', 'offline']
        with patch.object(sys, 'argv', args), patch.object(run.Client, 'check'), patch.object(run.Client, 'complete', fake_complete):
            try:
                run.main()
            except SystemExit as error:
                assert error.code == 1
            else:
                raise AssertionError('Individual failure must produce nonzero exit')
        manifest = json.loads((output / 'manifest.json').read_text())
        assert manifest['counts'] == {'execution_error': 1, 'complete': 19} or manifest['counts'] == {'complete': 19, 'execution_error': 1}
        assert len(sent) == 20 and len(manifest['entries']) == 20
        for entry in manifest['entries']:
            path = Path(entry['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
            data = json.loads(path.read_text());expected = data.pop('content_hash');assert digest(data) == expected
        with patch.object(sys, 'argv', args), patch.object(run.Client, 'check'):
            try:
                run.main()
            except AssertionError:
                pass
            else:
                raise AssertionError('Existing attempts must forbid a duplicate launch')
    print('PASS: twenty distinct cases, one isolated failure, hashes verified, duplicate run refused; only messages sent to model')


if __name__ == '__main__':
    main()
