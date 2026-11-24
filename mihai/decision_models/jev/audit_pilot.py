"""Check saved Jev pilot identities and probabilities without further API calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
package = project / 'releases/jev-variants-4090274c5245883d'
sys.path.insert(0, str(package))
import run_jev as jev

config = json.loads((package / 'config.json').read_text())
glide_package = Path(config['glide_package'])
sys.path.insert(0, str(glide_package))
import run_variants as variants

source = json.loads((glide_package / 'config.json').read_text())
base = variants.setup(source)
out = Path(config['output_dir'])
ready = base.read_json(out / 'ready.json')
assert all(ready[k] == v for k, v in jev.fingerprints(base, config).items())
accounting = subprocess.check_output(['sacct', '-j', '34391510', '-X', '-n', '-P',
                                    '-o', 'JobID,State,ExitCode,Elapsed'], text=True).strip()
assert accounting.split('|')[:3] == ['34391510', 'COMPLETED', '0:0'], accounting

# Stream the pretty-printed JSON array: retain only the shortest/longest case per view.
# This avoids loading the entire large input inventory on the login node.
extremes = {}; lines = None; sha = hashlib.sha256(); count = 0
with (Path(source['output_dir']) / 'inputs.json').open('rb') as stream:
    for raw in stream:
        sha.update(raw)
        if raw == b'  {\n': lines = []
        if lines is not None: lines.append(raw)
        if raw in (b'  },\n', b'  }\n'):
            case = json.loads(b''.join(lines).decode().rstrip().removesuffix(','))
            assert case['index'] == count
            assert base.digest({k: v for k, v in case.items() if k != 'sha256'}) == case['sha256']
            group = extremes.setdefault(case['scope'], [case, case])
            if case['full_tokens'] < group[0]['full_tokens']: group[0] = case
            if case['full_tokens'] > group[1]['full_tokens']: group[1] = case
            count += 1; lines = None
assert count == 450 and sha.hexdigest() == config['inputs_sha256']
selected = {c['index']: c for pair in extremes.values() for c in pair}
assert len(selected) == 6
report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'scheduler': accounting,
          'pilot_passed': False, 'full_complete': 0, 'chunks_complete': 0,
          'summaries_complete': 0, 'summaries_blocked': 0, 'full_inputs': []}
summary_scopes = set()

for i, case in sorted(selected.items()):
    path = out / 'full' / f'{i:03d}' / 'result.json'
    identity = jev.request_identity(base, config, case, case['full_request'], case['scope'] in ['cot', 'all'])
    row = jev.result_at(base, path, identity)
    assert row['status'] == 'complete'
    distribution = base.sampling_distribution(row['probabilities'], 0.6, 0.9)
    assert row['draws'] == base.draw_answers(distribution, f"{case['item_id']}:{case['told']}", 0, 4)
    report['full_complete'] += 1
    report['full_inputs'].append({'case': i, 'scope': case['scope'], 'usage': row['usage'],
                                 'seconds': row['seconds'], 'letter': row['letter']})
    for part in case['chunks']:
        path = out / 'chunks' / f'{i:03d}' / f"{part['index']:03d}.json"
        identity = jev.request_identity(base, config, case, part['glide_request'], False)
        assert jev.result_at(base, path, identity)['status'] == 'complete'
        report['chunks_complete'] += 1
    path = out / 'summaries' / f'{i:03d}' / 'result.json'
    if path.exists():
        request = jev.summary_input(base, source, case)
        assert request is not None
        identity = jev.request_identity(base, config, case, request, False)
        assert jev.result_at(base, path, identity)['status'] == 'complete'
        report['summaries_complete'] += 1
        summary_scopes.add(case['scope'])
    else:
        assert base.read_json(path.parent / 'blocked.json')['status'] == 'blocked'
        report['summaries_blocked'] += 1
assert summary_scopes == {'action', 'cot', 'all'}
report['pilot_passed'] = True
base.write_json(project / 'logs/jev-api-smoke-audit-34391510.json', report)
print(json.dumps(report), flush=True)
