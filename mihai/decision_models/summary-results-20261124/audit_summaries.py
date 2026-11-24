"""Offline terminal audit of Qwen summaries and the two downstream monitors."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
package = project / 'releases/decision-variants-d98ee84c398bee9b'
jev_package = project / 'releases/jev-variants-4090274c5245883d'
sys.path.insert(0, str(jev_package))
import run_jev as jev
sys.path.insert(0, str(package))
import run_variants as variants
from aggregation import validate_probabilities

config = json.loads((package / 'config.json').read_text())
jconfig = json.loads((jev_package / 'config.json').read_text())
assert hashlib.sha256((package / 'source-manifest.json').read_bytes()).hexdigest() == jconfig['glide_manifest_sha256']
assert hashlib.sha256((jev_package / 'source-manifest.json').read_bytes()).hexdigest() == '4090274c5245883d97f411c3a33c0fb9f4ae75f58fb0a7a16c065314530c67ff'
files = json.loads((jev_package / 'source-manifest.json').read_text())['files']
assert set(files) | {'source-manifest.json'} == {str(p.relative_to(jev_package)) for p in jev_package.rglob('*') if p.is_file()}
assert all(hashlib.sha256((jev_package / f).read_bytes()).hexdigest() == sha for f, sha in files.items())
base = variants.setup(config)
out = Path(config['output_dir'])
jout = Path(jconfig['output_dir'])
ready = base.read_json(out / 'ready.json')
assert ready['config_sha256'] == base.digest(config)
assert all(base.read_json(jout / 'ready.json')[k] == v for k, v in jev.fingerprints(base, jconfig).items())
collections, items = base.load_items(config)
pairs = {p.key: p for p in base.make_pairs(items)}
assert len(pairs) == 150
for item in items:
    item._raw = None

accounting = subprocess.check_output(['sacct', '-S', '2026-11-23', '-j',
    '34371577,34371590,34371591,34391867,34391868', '-X', '-n', '-P',
    '-o', 'JobID,State,ExitCode,Elapsed'], text=True).strip()
assert not any(s in accounting for s in ['RUNNING', 'PENDING', 'COMPLETING'])
records = defaultdict(list)
summary_counts = Counter()
failure_reasons = Counter()
failed_requests = []
hashes = {}
seen = set()
count = 0
sha = hashlib.sha256()
lines = None

with (out / 'inputs.json').open('rb') as stream:
    for raw in stream:
        sha.update(raw)
        if raw == b'  {\n': lines = []
        if lines is not None: lines.append(raw)
        if raw not in (b'  },\n', b'  }\n'): continue
        case = json.loads(b''.join(lines).decode().rstrip().removesuffix(','))
        lines = None
        assert case['index'] == count
        assert base.digest({k: v for k, v in case.items() if k != 'sha256'}) == case['sha256']
        key = (case['scope'], case['item_id'], case['told'])
        assert key not in seen and key[1:] in pairs
        seen.add(key)
        directory = f'{count:03d}'
        identity = {'config': base.digest(config), 'case': case['sha256']}
        complete = True
        for part in case['chunks']:
            path = out / 'qwen' / directory / 'summaries' / f"{part['index']:03d}.json"
            row = base.read_json(path)
            assert row['identity_sha256'] == base.digest({**identity, 'summary_prompt': part['summary_prompt']})
            summary_counts[row['status']] += 1
            call_key = base.digest({'prompt': part['summary_prompt'], 'seed': config['seed']})
            call_path = out / 'qwen' / directory / 'calls' / (call_key + '.json')
            call = base.read_json(call_path)
            assert call['identity_sha256'] == base.digest({**identity, 'prompt': part['summary_prompt'], 'seed': config['seed']})
            assert call['status'] == 'complete'
            response = call['response']
            if row['status'] == 'complete':
                assert response['finish_reason'] == 'stop'
                assert row['text'] == response['text'] and row['text'].strip()
                assert row['usage'] == response['usage']
                assert base.h.parse_verdict(row['text']) is None
            else:
                assert row['status'] == 'failed'
                complete = False
                failure_reasons[response['finish_reason']] += 1
                failed_requests.append({'case': count, 'scope': case['scope'], 'chunk': part['index'],
                                        'finish_reason': response['finish_reason'], 'usage': response['usage']})
            hashes[str(path.relative_to(project))] = base.file_hash(path)
        request = jev.summary_input(base, config, case)
        assert (request is not None) == complete
        for model, folder, stage in [('glide', out, 'glide-summaries'), ('jev', jout, 'summaries')]:
            path = folder / stage / directory / 'result.json'
            if complete:
                if model == 'jev':
                    row = jev.result_at(base, path, jev.request_identity(base, jconfig, case, request, False))
                else:
                    row = base.read_json(path)
                    assert row['identity_sha256'] == base.digest({**identity, 'request': request})
                    probabilities = validate_probabilities(row['probabilities'])
                    answer = row['response']['answers']['verdict']
                    assert answer['probabilities'] == probabilities
                    assert answer['choice'] == row['letter'] == max('ABCD', key=probabilities.get)
                assert row['status'] == 'complete' and row['detected'] == (row['letter'] == 'A')
                status, letter, detected = 'complete', row['letter'], row['detected']
            else:
                assert not path.exists()
                path = path.parent / 'blocked.json'
                assert base.read_json(path)['status'] == 'blocked'
                status, letter, detected = 'blocked', None, None
            hashes[str(path.relative_to(project))] = base.file_hash(path)
            records[model + '-' + case['scope']].append({'item_id': case['item_id'], 'told': case['told'],
                    'sample': 0, 'status': status, 'letter': letter, 'detected': detected})
        count += 1

assert count == 450 and sha.hexdigest() == jconfig['inputs_sha256'] == ready['inputs_sha256']
assert sum(summary_counts.values()) == 2834
report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'audit_passed': True,
          'scheduler': accounting, 'inputs_sha256': sha.hexdigest(),
          'qwen_summary_counts': dict(summary_counts), 'failure_finish_reasons': dict(failure_reasons),
          'failed_requests': failed_requests, 'results': {}, 'matched_references': {}}
for name, values in records.items():
    model, scope = name.split('-')
    collected = base.metrics.collect(values, pairs)
    points = base.metrics.point_estimates(collected, pairs)
    folder = out if model == 'glide' else jout
    prefix = scope + ('-glide-summaries' if model == 'glide' else '-summaries')
    saved = base.read_json(folder / 'scores' / (prefix + '-metrics.json'))
    assert base.digest(points) == base.digest(saved['point_estimates'])
    saved_records = base.read_json(folder / 'scores' / (prefix + '-records.json'))
    assert base.metrics.collect(saved_records, pairs) == collected
    report['results'][name] = {'states': dict(Counter(v['status'] for v in values)), 'points': points}
    # Compare earlier full/chunk scores on exactly the cases with complete summaries.
    valid_keys = {(r['item_id'], r['told']) for r in values if r['status'] == 'complete'}
    reference = out / 'audits/glide-completed-34428767' if model == 'glide' else jout / 'audits/completed-34426786'
    for method in ['full' if model == 'glide' else 'full-greedy', 'mean']:
        old = base.read_json(reference / 'scores' / f'{scope}-{method}-records.json')
        selected = [r for r in old if (r['item_id'], r['told']) in valid_keys]
        assert len(selected) == len(valid_keys)
        report['matched_references'][name + '-' + method] = base.metrics.point_estimates(base.metrics.collect(selected, pairs), pairs)
for scope in ['action', 'cot', 'all']:
    a = {(r['item_id'], r['told']) for r in records['glide-' + scope] if r['status'] == 'complete'}
    b = {(r['item_id'], r['told']) for r in records['jev-' + scope] if r['status'] == 'complete'}
    assert a == b
destination = project / 'mihai/decision_models/runs' / ('summary-audit-' + os.environ['SLURM_JOB_ID'])
assert not destination.exists()
base.write_json(destination / 'audit.json', report)
base.write_json(destination / 'artifact-hashes.json', hashes)
print(json.dumps({'audit_passed': True, 'output_dir': str(destination)}), flush=True)
