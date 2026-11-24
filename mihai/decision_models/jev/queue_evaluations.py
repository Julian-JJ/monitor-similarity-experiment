"""Submit the authorized Jev stages after an inspected, successful pilot.

Run on the cluster. Submission records contain paths and settings, never the key.
All stages share one cache lock, so the jobs run in sequence.
"""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
logs = project / 'logs'
python = str(project / 'envs/monitor-research/bin/python')
launcher = project / 'releases/jev-private-launcher-bbb8cebc31a89653/launch_private.py'
assert hashlib.sha256(launcher.read_bytes()).hexdigest() == 'bbb8cebc31a8965397f71c40f058cd7c4d32d7e224df8b6d3ae14fbf6d4f97e0'
audit = json.loads((logs / 'jev-api-smoke-audit-34391510.json').read_text())
assert audit['pilot_passed'] and audit['full_complete'] == 6


def submit(stage, dependency):
    name = 'decision-variants-20261123-jev-' + stage
    command = shlex.join([python, '-B', str(launcher), stage])
    spec = {'logs': str(logs), 'name': name,
            'source_manifest_sha256': '4090274c5245883d97f411c3a33c0fb9f4ae75f58fb0a7a16c065314530c67ff',
            'arguments': ['--account=cpsc4880', '--partition=day', '--nodes=1', '--ntasks=1',
                          '--cpus-per-task=4', '--mem=48G', '--time=12:00:00', '--no-requeue',
                          '--dependency=' + dependency, '--kill-on-invalid-dep=yes',
                          '--output=' + str(logs / f'jev-{stage}-%j.log'), '--wrap=' + command]}
    path = logs / f'jev-{stage}-submission-spec.json'
    path.write_text(json.dumps(spec, indent=2) + '\n')
    result = subprocess.run([python, '-B', str(logs / 'submit_job.py'), str(path)],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Submission failed; reconcile the durable marker before trying again: ' + stage)
    receipt = json.loads(result.stdout)
    receipt = receipt.get('existing_receipt', receipt)
    print(json.dumps({'stage': stage, 'job_id': receipt['job_id'], 'dependency': dependency}), flush=True)
    return receipt['job_id']


full = submit('full', 'afterok:34391510')
chunks = submit('chunks', 'afterok:34391510,afterany:' + full)
# Wait for the identical Qwen summaries used in the GLiDE comparison.
summaries = submit('summaries', 'afterok:34391510,afterany:' + chunks + ':34371577')
score = submit('score', 'afterany:' + summaries)
