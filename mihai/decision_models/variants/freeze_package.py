"""Run once on a new deployment copy after finalizing config.json. Never edit a release."""
import hashlib
import json
import sys
from pathlib import Path

root=Path(sys.argv[1]).resolve()
manifest=root/'source-manifest.json'
if manifest.exists(): raise SystemExit('Already frozen; use a new deployment directory')
if not (root/'config.json').exists(): raise SystemExit('Finalize config.json first')
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in sorted(root.rglob('*')) if p.is_file()}
with manifest.open('x') as f:
    json.dump({'files':files},f,indent=2)
    f.write('\n')
print(hashlib.sha256(manifest.read_bytes()).hexdigest())
