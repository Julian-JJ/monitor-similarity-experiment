"""Durable one-shot Slurm submission; run on the cluster with a JSON spec path."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
import uuid

spec=json.loads(Path(sys.argv[1]).read_text())
logs=Path(spec['logs']); logs.mkdir(parents=True,exist_ok=True)
prefix=logs/spec['name']
attempt=Path(str(prefix)+'.attempt.json'); receipt=Path(str(prefix)+'.submission.json')

def write(path,value):
    temporary=Path(str(path)+'.tmp')
    with temporary.open('w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

with (logs/'decision-variants-submission.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    queue=subprocess.run(['squeue','-u',os.environ['USER'],'-h','-o','%i|%j|%T|%k'],check=True,capture_output=True,text=True,timeout=20).stdout
    accounting=subprocess.run(['sacct','-u',os.environ['USER'],'-S','2026-11-23','-X','-n','-P','-o','JobID,JobName%80,State,Comment%100'],check=True,capture_output=True,text=True,timeout=20).stdout
    prior={p.name:json.loads(p.read_text()) for p in logs.glob('decision-variants-*.submission.json')}
    if receipt.exists():
        print(json.dumps({'existing_receipt':json.loads(receipt.read_text()),'queue':queue,'accounting':accounting}));sys.exit(0)
    if attempt.exists(): raise SystemExit('Attempt exists without receipt: reconcile UUID with Slurm; do not resubmit')
    if any(spec['name']==row.split('|')[1].strip() for row in (queue+accounting).splitlines() if '|' in row):
        raise SystemExit('Job with this name already exists in Slurm; reconcile it instead of resubmitting')
    intent=str(uuid.uuid4())
    command=['sbatch','--parsable',f"--job-name={spec['name']}",f'--comment=decision-variants:{intent}',*spec['arguments']]
    record={'status':'attempting','intent':intent,'created_utc':datetime.now(timezone.utc).isoformat(),
            'command':command,'source_manifest_sha256':spec['source_manifest_sha256'],
            'prior_receipts':{k:v.get('job_id') for k,v in prior.items()},'queue_before':queue,'accounting_before':accounting}
    write(attempt,record)
    # After this marker, any timeout or malformed response requires reconciliation.
    result=subprocess.run(command,capture_output=True,text=True,timeout=45)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():
        write(attempt,{**record,'status':'uncertain','stdout':result.stdout,'stderr':result.stderr})
        raise SystemExit('Submission did not return a confirmed job ID; reconcile the attempt marker')
    record.update(status='submitted',job_id=job,submitted_utc=datetime.now(timezone.utc).isoformat(),stderr=result.stderr)
    write(receipt,record);write(attempt,record)
    print(json.dumps(record))
