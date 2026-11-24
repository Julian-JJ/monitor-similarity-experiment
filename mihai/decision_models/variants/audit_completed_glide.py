"""Offline audit and scoring for completed GLiDE full and chunk comparisons."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
package = project / 'releases/decision-variants-d98ee84c398bee9b'
manifest_sha = 'd98ee84c398bee9b90f66132b15a8c5fd53476d97534a0d5a1f9569cbde0a616'
assert hashlib.sha256((package / 'source-manifest.json').read_bytes()).hexdigest() == manifest_sha
sys.path.insert(0, str(package))
import run_variants as variants
from aggregation import aggregate, validate_probabilities

config = json.loads((package / 'config.json').read_text())
base = variants.setup(config)
out = Path(config['output_dir'])
ready = base.read_json(out / 'ready.json')
assert ready['config_sha256'] == base.digest(config)
accounting = subprocess.check_output(['sacct', '-S', '2026-11-23', '-j', '34371578',
                                    '-X', '-n', '-P', '-o', 'JobID,State,ExitCode,Elapsed'], text=True).strip()
assert accounting.split('|')[:3] == ['34371578', 'COMPLETED', '0:0']
collections, items = base.load_items(config)
pairs = {pair.key: pair for pair in base.make_pairs(items)}
assert len(items) == 75 and len(pairs) == 150
for item in items:
    item._raw = None

reused = {}
old_requests = {}
for scope, folder in config['reuse'].items():
    folder = Path(folder)
    for name, sha in ready['reuse_hashes'][scope].items():
        assert base.file_hash(folder / name) == sha
    assert base.read_json(folder / 'ready.json')['collection_hashes'] == ready['collection_hashes']
    old_requests[scope] = {(r['item_id'], r['told']): r['request_sha256']
                           for r in base.read_json(folder / 'inputs.json')}
    reused[scope] = base.read_json(folder / 'greedy-records.json')
    assert len(reused[scope]) == len(old_requests[scope]) == 150
    assert {(r['item_id'], r['told']) for r in reused[scope]} == set(pairs)
    assert all(r['status'] == 'complete' for r in reused[scope])

records = defaultdict(list)
artifact_hashes = {}
expected_chunks = set()
seen = set()


def verify_result(path, identity, tokens):
    row = base.read_json(path)
    assert row['identity_sha256'] == base.digest(identity)
    assert row['status'] == 'complete'
    probabilities = validate_probabilities(row['probabilities'])
    winner = max('ABCD', key=probabilities.get)
    answer = row['response']['answers']['verdict']
    assert answer['probabilities'] == probabilities and answer['choice'] == winner == row['letter']
    assert row['detected'] == (winner == 'A')
    assert row['response']['usage'] == {'input_tokens': tokens, 'output_tokens': 0}
    artifact_hashes[str(path.relative_to(out))] = base.file_hash(path)
    return row


def record(case, method, row):
    records[case['scope'] + '-' + method].append({
        'item_id': case['item_id'], 'told': case['told'], 'sample': 0,
        'status': 'complete', 'letter': row.get('letter'), 'detected': row['detected']})


# Stream prepared cases to avoid retaining every long transcript in memory.
lines = None
sha = hashlib.sha256()
count = 0
with (out / 'inputs.json').open('rb') as stream:
    for raw in stream:
        sha.update(raw)
        if raw == b'  {\n':
            lines = []
        if lines is not None:
            lines.append(raw)
        if raw not in (b'  },\n', b'  }\n'):
            continue
        case = json.loads(b''.join(lines).decode().rstrip().removesuffix(','))
        lines = None
        assert case['index'] == count
        assert base.digest({k: v for k, v in case.items() if k != 'sha256'}) == case['sha256']
        key = (case['scope'], case['item_id'], case['told'])
        assert key not in seen and key[1:] in pairs
        seen.add(key)
        identity = {'config': base.digest(config), 'case': case['sha256']}
        directory = f"{case['index']:03d}"
        if case['scope'] in reused:
            assert old_requests[case['scope']][key[1:]] == base.digest(case['full_request'])
        else:
            row = verify_result(out / 'glide-full' / directory / 'result.json',
                                {**identity, 'request': case['full_request']}, case['full_tokens'])
            record(case, 'full', row)
        chunks = []
        for part in case['chunks']:
            path = out / 'glide-chunks' / directory / f"{part['index']:03d}.json"
            row = verify_result(path, {**identity, 'request': part['glide_request']}, part['glide_tokens'])
            chunks.append({**row, 'index': part['index']})
            expected_chunks.add(path)
        combined = aggregate(chunks, len(case['chunks']), config['threshold'])
        assert combined == base.read_json(out / 'glide-chunks' / directory / 'aggregates.json')
        for rule in ['max', 'mean']:
            record(case, rule, combined[rule])
        count += 1

assert count == 450 and sha.hexdigest() == ready['inputs_sha256']
assert len(expected_chunks) == 2834
assert expected_chunks == {p for p in (out / 'glide-chunks').glob('*/*.json') if p.name != 'aggregates.json'}
assert len(list((out / 'glide-full').glob('*/result.json'))) == 150
for scope in reused:
    records[scope + '-full'] = reused[scope]

destination = out / 'audits' / ('glide-completed-' + os.environ['SLURM_JOB_ID'])
assert not destination.exists()
results = {}
for name, values in sorted(records.items()):
    assert len(values) == 150
    collected = base.metrics.collect(values, pairs)
    assert len(collected) == 150
    metrics = {'point_estimates': base.metrics.point_estimates(collected, pairs),
               'intervals': base.metrics.bootstrap_intervals(collected, pairs, n=2000, seed=0)}
    base.write_json(destination / 'scores' / (name + '-records.json'), values)
    base.write_json(destination / 'scores' / (name + '-metrics.json'), metrics)
    pooled = metrics['point_estimates']['pooled']
    pos = pooled['counts']['positive']
    clean = pooled['counts']['clean_negative']
    results[name] = {'tpr': pooled['metrics']['tpr'][0],
                     'fpr_clean': 1 - pooled['metrics']['tnr_clean'][0],
                     'gmean2_clean': pooled['metrics']['gmean2_clean'][0],
                     'primary_accuracy': (pos['detected'] + clean['valid'] - clean['detected']) / (pos['valid'] + clean['valid']),
                     'counts': pooled['counts'], 'coverage': pooled['metrics']['coverage'][0]}
report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'audit_passed': True,
          'scheduler': accounting, 'inputs_sha256': ready['inputs_sha256'],
          'source_manifest_sha256': manifest_sha, 'collection_hashes': ready['collection_hashes'],
          'audit_script_sha256': base.file_hash(Path(__file__)), 'reused_full_requests': 300,
          'new_full_requests_verified': 150, 'chunk_requests_verified': 2834,
          'results': results, 'output_dir': str(destination)}
base.write_json(destination / 'artifact-hashes.json', artifact_hashes)
base.write_json(destination / 'audit.json', report)
print(json.dumps({'audit_passed': True, 'output_dir': str(destination)}), flush=True)
