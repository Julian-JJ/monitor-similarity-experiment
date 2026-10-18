"""Mirror only this experiment's compact records, never raw model responses."""
import json
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
files = {'state.json': (BASE/'state.json').read_text()}
files.update({str(p.relative_to(BASE)): p.read_text()
              for p in (BASE/'records').iterdir()
              if p.is_file() and p.suffix in ('.json', '.py', '.md')})
for name in ('results.json', 'report.md'):
    if (BASE/name).exists():
        files[name] = (BASE/name).read_text()
code = '''import hashlib,json,os,pathlib
base=pathlib.Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
files=PAYLOAD
for root in [base/'test_rollouts_2',base/'monitor-similarity-experiment/mihai/test_rollouts_2']:
 for rel,content in files.items():
  p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists() and p.read_text()==content:continue
  if p.name in ('submission.json','intent.json') and p.exists():
   assert json.loads(p.read_text())==json.loads(content), 'Cannot alter submission identity'
   continue
  temp=p.with_name(p.name+'.sync-tmp')
  with temp.open('w') as f:f.write(content);f.flush();os.fsync(f.fileno())
  os.replace(temp,p)
print(json.dumps({'mirrored_files':len(files),'destinations':2}))
'''.replace('PAYLOAD', repr(files))
result = subprocess.run([
    'ssh', '-S', '/private/tmp/mihai-yale-ssh.jWuHMd/control',
    '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-T',
    'cpsc4880_mae73@bouchet.ycrc.yale.edu',
    'PYTHONDONTWRITEBYTECODE=1 /nfs/roberts/project/cpsc4880/cpsc4880_mae73/envs/monitor-research/bin/python -B -'],
    input=code, capture_output=True, text=True, timeout=45)
result.check_returncode()
print(result.stdout)
