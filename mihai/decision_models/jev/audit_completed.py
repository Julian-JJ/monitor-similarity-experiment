"""Audit and score finished Jev full/chunk stages without sending API requests.

Run as a CPU job. Keep this report separate from the queued final summary score.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
package = project / 'releases/jev-variants-4090274c5245883d'
manifest_sha = '4090274c5245883d97f411c3a33c0fb9f4ae75f58fb0a7a16c065314530c67ff'
assert hashlib.sha256((package / 'source-manifest.json').read_bytes()).hexdigest() == manifest_sha
files = json.loads((package / 'source-manifest.json').read_text())['files']
assert {str(p.relative_to(package)) for p in package.rglob('*') if p.is_file()} == set(files) | {'source-manifest.json'}
assert all(hashlib.sha256((package / name).read_bytes()).hexdigest() == sha for name, sha in files.items())
sys.path.insert(0, str(package))
import run_jev as jev

config = json.loads((package / 'config.json').read_text())
glide_package = Path(config['glide_package'])
assert hashlib.sha256((glide_package / 'source-manifest.json').read_bytes()).hexdigest() == config['glide_manifest_sha256']
sys.path.insert(0, str(glide_package))
import run_variants as variants
from aggregation import aggregate

source = json.loads((glide_package / 'config.json').read_text())
base = variants.setup(source)
out = Path(config['output_dir'])
ready = base.read_json(out / 'ready.json')
assert all(ready[k] == v for k, v in jev.fingerprints(base, config).items())
accounting = subprocess.check_output(['sacct', '-S', '2026-11-23', '-j', '34391865,34391866',
                                    '-X', '-n', '-P', '-o', 'JobID,State,ExitCode,Elapsed'], text=True)
rows = [row.split('|') for row in accounting.splitlines() if row.strip()]
assert {row[0] for row in rows} == {'34391865', '34391866'}
assert all(row[1:3] == ['COMPLETED', '0:0'] for row in rows)

collections, items = base.load_items(source)
pairs = {pair.key: pair for pair in base.make_pairs(items)}
assert len(items) == 75 and len(pairs) == 150
for item in items:
    item._raw = None  # The scorer needs labels, not retained transcripts.

records = defaultdict(list)
timing = defaultdict(list)
usage = defaultdict(Counter)
scope_counts = Counter()
expected_files = {'full': set(), 'chunks': set()}
seen = set()


def check_result(case, request, path, long_context, stage):
    identity = jev.request_identity(base, config, case, request, long_context)
    row = jev.result_at(base, path, identity)
    assert row['status'] == 'complete', str(path)
    distribution = base.sampling_distribution(row['probabilities'], 0.6, 0.9)
    assert row['sampling_probabilities'] == distribution
    assert row['draws'] == base.draw_answers(distribution, f"{case['item_id']}:{case['told']}", 0, 4)
    name = stage + '-' + case['scope']
    timing[name].append(row['seconds'])
    usage[name].update(row['usage'])
    expected_files[stage].add(path)
    return row


def add_record(case, method, detected, letter=None, sample=0):
    records[case['scope'] + '-' + method].append({
        'item_id': case['item_id'], 'told': case['told'], 'sample': sample,
        'status': 'complete', 'letter': letter, 'detected': detected})


# Read one array element at a time instead of loading the large input file.
lines = None
sha = hashlib.sha256()
count = 0
with (Path(source['output_dir']) / 'inputs.json').open('rb') as stream:
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
        identity = (case['scope'], case['item_id'], case['told'])
        assert identity not in seen and (case['item_id'], case['told']) in pairs
        seen.add(identity)
        scope_counts[case['scope']] += 1
        directory = f"{case['index']:03d}"
        row = check_result(case, case['full_request'], out / 'full' / directory / 'result.json',
                           case['scope'] in ['cot', 'all'], 'full')
        add_record(case, 'full-greedy', row['detected'], row['letter'])
        for sample, draw in enumerate(row['draws']):
            add_record(case, 'full-sampled', draw['letter'] == 'A', draw['letter'], sample)
        chunks = []
        for part in case['chunks']:
            path = out / 'chunks' / directory / f"{part['index']:03d}.json"
            row = check_result(case, part['glide_request'], path, False, 'chunks')
            chunks.append({**row, 'index': part['index']})
        combined = aggregate(chunks, len(case['chunks']), 0.5)
        for rule in ['max', 'mean']:
            add_record(case, rule, combined[rule]['detected'])
        count += 1

assert count == 450 and sha.hexdigest() == config['inputs_sha256']
assert dict(scope_counts) == {'action': 150, 'cot': 150, 'all': 150}
assert len(expected_files['chunks']) == 2834
for stage, expected in expected_files.items():
    assert set((out / stage).glob('*/*.json')) == expected

destination = out / 'audits' / ('completed-' + os.environ['SLURM_JOB_ID'])
assert not destination.exists(), 'Preserve previous reports; do not overwrite.'
results = {}
for name, values in sorted(records.items()):
    collected = base.metrics.collect(values, pairs)
    assert len(collected) == 150
    metrics = {'point_estimates': base.metrics.point_estimates(collected, pairs),
               'intervals': base.metrics.bootstrap_intervals(collected, pairs, n=2000, seed=0)}
    base.write_json(destination / 'scores' / (name + '-records.json'), values)
    base.write_json(destination / 'scores' / (name + '-metrics.json'), metrics)
    pooled = metrics['point_estimates']['pooled']
    positive = pooled['counts']['positive']
    clean = pooled['counts']['clean_negative']
    results[name] = {'tpr': pooled['metrics']['tpr'][0],
                     'fpr_clean': 1 - pooled['metrics']['tnr_clean'][0],
                     'gmean2_clean': pooled['metrics']['gmean2_clean'][0],
                     'primary_accuracy': (positive['detected'] + clean['valid'] - clean['detected']) / (positive['valid'] + clean['valid']),
                     'counts': pooled['counts'], 'coverage': pooled['metrics']['coverage'][0]}

report = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'audit_passed': True,
          'source_manifest_sha256': manifest_sha, 'inputs_sha256': config['inputs_sha256'],
          'audit_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'scheduler': accounting.strip(), 'full_requests_verified': 450, 'chunk_requests_verified': 2834,
          'collection_hashes': {c.name: c.manifest_sha256 for c in collections},
          'timing': {name: {'requests': len(values), 'total_api_seconds': sum(values),
                            'mean_api_seconds': sum(values) / len(values), 'usage': dict(usage[name])}
                     for name, values in timing.items()},
          'summary_condition': 'Excluded: production is still queued behind Qwen.',
          'results': results, 'output_dir': str(destination)}
base.write_json(destination / 'audit.json', report)
print(json.dumps({'audit_passed': True, 'output_dir': str(destination)}), flush=True)
