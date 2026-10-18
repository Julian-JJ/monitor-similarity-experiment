"""Read-only cluster observation. Emits metadata only, never reasoning text."""
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73/test_rollouts_2')
JOB = '29910578'
output = ROOT / 'runs' / JOB
result = {'observed_at':datetime.now(timezone.utc).isoformat(),'job_id':int(JOB)}
for key, args in [
    ('squeue',['squeue','-j',JOB,'-h','-o','%i|%T|%M|%R|%k']),
    ('sacct',['sacct','-S','2026-10-16','-j',JOB,'-n','-P',
              '-o','JobID,State,ExitCode,Elapsed,Start,End,NodeList'])]:
    r = subprocess.run(args,capture_output=True,text=True,timeout=15)
    result[key] = {'returncode':r.returncode,'stdout':r.stdout.strip(),'stderr':r.stderr.strip()}
result['receipt'] = json.loads((ROOT/'records/submission.json').read_text())['job_id']
result['counts'] = dict(Counter(json.loads(p.read_text())['status'] for p in (output/'raw').glob('*.json')))
progress = output/'progress.json'
if progress.exists():
    result['completed'] = json.loads(progress.read_text())['completed']
for name, limit in [('status.txt',8),('gpu.csv',3),('server.log',5)]:
    path=output/name
    if path.exists():
        with path.open('rb') as f:
            f.seek(max(0,path.stat().st_size-12000));text=f.read().decode(errors='replace')
        result[name] = '\n'.join(text.splitlines()[-limit:])
slurm=ROOT/'logs'/('slurm-'+JOB+'.log')
if slurm.exists():
    result['slurm_tail']=subprocess.run(['tail','-n','8',str(slurm)],capture_output=True,text=True,timeout=5).stdout
manifest=output/'manifest.json'
if manifest.exists():
    result['manifest']=json.loads(manifest.read_text())
print(json.dumps(result))
