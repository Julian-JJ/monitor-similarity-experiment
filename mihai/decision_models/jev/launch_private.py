"""Load the private cluster key into the child environment; never print it."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

package = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73/releases/jev-variants-4090274c5245883d')
manifest = package / 'source-manifest.json'
expected = '4090274c5245883d97f411c3a33c0fb9f4ae75f58fb0a7a16c065314530c67ff'
if hashlib.sha256(manifest.read_bytes()).hexdigest() != expected:
    raise SystemExit('Wrong Jev package manifest')
files = json.loads(manifest.read_text())['files']
if {str(p.relative_to(package)) for p in package.rglob('*') if p.is_file()} != set(files) | {'source-manifest.json'}:
    raise SystemExit('Jev package inventory changed')
if any(hashlib.sha256((package / n).read_bytes()).hexdigest() != sha for n, sha in files.items()):
    raise SystemExit('Jev source file changed')

stage = sys.argv[1]
environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
if stage not in ['prepare', 'score']:
    key_file = Path.home() / '.config/monitor-experiments/jev.key'
    info = key_file.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise SystemExit('The credential file must be owned by this account and private')
    key = key_file.read_text().strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('Credential is empty or contains whitespace')
    environment['TYPESAFE_API_KEY'] = key

# execve replaces this launcher; the key is an environment value, not a command argument.
os.execve(sys.executable, [sys.executable, '-B', str(package / 'run_jev.py'),
          stage, str(package / 'config.json'), *sys.argv[2:]], environment)
