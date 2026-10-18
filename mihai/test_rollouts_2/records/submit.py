"""Execute on cluster only, once, after verified preparation. Durable submission."""
import fcntl
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
EXP = ROOT / 'test_rollouts_2'
RELEASE = EXP / 'releases/41e5261de745d76c'
EXPECTED = '41e5261de745d76cf070fa0f6729ed54e6f5d06435341497030d37acbcc15fc3'


def write(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as f:
        json.dump(data, f, indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def command(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=25)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def main(intent_id):
    import uuid
    assert str(uuid.UUID(intent_id)) == intent_id
    with (ROOT / 'logs/qwen-token-retry-submission.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        receipt = EXP / 'records/submission.json'
        attempt = EXP / 'records/attempt.json'
        if receipt.exists():
            print(receipt.read_text());return
        assert not attempt.exists(), 'Existing attempt without receipt requires reconciliation; no resubmission'
        queue = command(['squeue','-u','cpsc4880_mae73','-h','-o','%i|%j|%T|%k'])
        assert not any('qwen' in line.lower() or 'test_rollouts_2' in line.lower() for line in queue.splitlines()), queue
        accounting = command(['sacct','-S','2026-10-16','-u','cpsc4880_mae73','-X','-n','-P',
                              '-o','JobID,JobName%80,State,ExitCode,Comment%120'])
        assert intent_id not in accounting, 'Intent already visible in accounting'
        history = {}
        for marker in (ROOT / 'logs').glob('qwen-*.attempt.json'):
            partner = marker.with_name(marker.name.replace('.attempt.json','.submission.json'))
            assert partner.exists(), 'Unresolved earlier submission marker: ' + str(marker)
            old, old_receipt = json.loads(marker.read_text()), json.loads(partner.read_text())
            assert old.get('intent_id') == old_receipt.get('intent_id')
            job = str(old_receipt['job_id'])
            rows = [line for line in accounting.splitlines() if line.startswith(job+'|')]
            assert len(rows) == 1 and rows[0].split('|')[2] in ('FAILED','TIMEOUT','COMPLETED','CANCELLED'), rows
            history[partner.name] = {'job_id':job, 'intent_id':old_receipt['intent_id']}
        assert hashlib.sha256((RELEASE/'release-manifest.json').read_bytes()).hexdigest() == EXPECTED
        preflight = json.loads((EXP/'records/preflight.json').read_text())
        assert preflight['release_sha256'] == EXPECTED and preflight['all_requests_fit_context']
        for name, digest in json.loads((RELEASE/'release-manifest.json').read_text())['files'].items():
            assert hashlib.sha256((RELEASE/name).read_bytes()).hexdigest() == digest
        args = ['sbatch','--parsable','--account=cpsc4880','--partition=gpu_h200',
            '--nodes=1','--ntasks=1','--gpus=h200:1','--cpus-per-task=8','--mem=96G',
            '--time=03:00:00','--no-requeue','--job-name=mihai-qwen-test-rollouts-2',
            '--comment=test-rollouts-2:'+intent_id,'--chdir='+str(RELEASE),
            '--output='+str(EXP/'logs/slurm-%j.log'), str(RELEASE/'run.sbatch'),str(RELEASE),EXPECTED]
        intent = {'experiment':'test_rollouts_2','intent_id':intent_id,'state':'submission_attempting',
            'attempted_at':datetime.now(timezone.utc).isoformat(),'release':str(RELEASE),
            'release_manifest_sha256':EXPECTED,'configuration_sha256':hashlib.sha256((RELEASE/'config.json').read_bytes()).hexdigest(),
            'selection_sha256':hashlib.sha256((RELEASE/'selection.json').read_bytes()).hexdigest(),
            'sbatch_command':args,'expected_requests':20,'distinct_problems':12,
            'queue_before_submission':queue,'accounting_before_submission':accounting,'prior_receipts':history,
            'authorization':'User requested separate test_rollouts_2 screening, two problems per candidate task type; no automatic retries.'}
        write(EXP/'records'/('intent-'+intent_id+'.json'),intent)
        write(attempt,intent)
        r = subprocess.run(args,capture_output=True,text=True,timeout=35)
        if r.returncode or not r.stdout.strip().split(';')[0].isdigit():
            intent.update(state='uncertain',stdout=r.stdout,stderr=r.stderr,returncode=r.returncode)
            write(attempt,intent)
            raise RuntimeError('Submission uncertain or rejected; reconcile before any future action')
        intent.update(job_id=int(r.stdout.strip().split(';')[0]),state='submitted',
            submitted_at=datetime.now(timezone.utc).isoformat(),sbatch_stdout=r.stdout.strip(),sbatch_stderr=r.stderr)
        write(receipt,intent)
        write(attempt,intent)
        print(json.dumps(intent))


if __name__ == '__main__':
    main(sys.argv[1])
