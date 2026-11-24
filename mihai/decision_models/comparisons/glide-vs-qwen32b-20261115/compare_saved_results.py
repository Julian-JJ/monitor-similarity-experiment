"""Compare saved verdicts only; no inference and no reasoning text in the report."""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
source = root / 'releases/glide-cot-20261115-c8f6c4e8'
sys.path.insert(0, str(source / 'mihai/decision_models'))
import run_evaluation as base
from monitor_experiment.costs import compute_by_monitor

base.verify_source()
config = base.read_json(source / 'mihai/decision_models/evaluation.json')
collections, items = base.load_items(config)
pairs = {p.key: p for p in base.make_pairs(items)}
qdir = Path('/nfs/roberts/project/cpsc4880/cpsc4880_as4833/runs/baseline')
manifest = base.read_json(qdir / 'manifest.json')
stored = base.read_json(qdir / 'metrics.json')
all_records = [json.loads(line) for line in (qdir / 'items.jsonl').read_text().splitlines()]
assert {k: v['manifest_sha256'] for k, v in manifest['rollout_sets'].items()} == {k: v['sha256'] for k, v in config['collections'].items()}
assert set(manifest['item_ids']) == {i.item_id for i in items}
expected_keys = {(i.item_id, told, s) for i in items for told in ['malicious', 'benign'] for s in range(4)}
qcells = {c['label']['scope']: c for c in manifest['cells'] if c['label']['monitor'] == 'qwen3-32b'}
assert set(qcells) == {'action', 'cot', 'all'}
qrecords, collected, rows = {}, {}, []

def report_row(model, scope, method, records, points, intervals=None):
    pooled = points['pooled']; m = pooled['metrics']; counts = pooled['counts']
    positive, clean = counts['positive'], counts['clean_negative']
    return {'model': model, 'scope': scope, 'method': method, 'judgments': len(records),
            'detection': m['tpr'][0], 'clean_false_alarm': 1 - m['tnr_clean'][0],
            'gmean2': m['gmean2_clean'][0],
            'positive_and_clean_accuracy': (positive['detected'] + clean['valid'] - clean['detected']) / (positive['valid'] + clean['valid']),
            'points': points, 'intervals': intervals}

for scope, cell in qcells.items():
    records = [r for r in all_records if r['cell_id'] == cell['cell_id']]
    assert len(records) == 600 and {(r['item_id'], r['told'], r['sample']) for r in records} == expected_keys
    assert all(r['status'] == 'complete' and r['letter'] in 'ABCD' and r['detected'] == (r['letter'] == 'A') for r in records)
    qrecords[scope] = records
    collected[('qwen', scope)] = base.metrics.collect(records, pairs)
    points = base.metrics.point_estimates(collected[('qwen', scope)], pairs)
    original = next(c for c in stored['cells'] if c['cell_id'] == cell['cell_id'])
    for told in ['malicious', 'benign', 'pooled']:
        assert points[told]['counts'] == original['results'][told]['counts']
        for metric, (value, reason) in points[told]['metrics'].items():
            assert value == original['results'][told]['metrics'][metric]['value']
    row = report_row('Qwen3-32B', scope, 'four independent sampled analyses', records, points)
    row['hierarchical_judgments'] = sum(r['hierarchical'] for r in records)
    row['model_requests'] = sum(r['model_requests'] for r in records)
    row['gmean2_interval'] = {k: original['results']['pooled']['metrics']['gmean2_clean'][k] for k in ['low', 'high']}
    rows.append(row)

runs = {'action': 'glide-actions-20261115-60611f0f', 'cot': 'glide-cot-20261115-c8f6c4e8'}
for scope, name in runs.items():
    folder = root / 'mihai/decision_models/runs' / name
    ready = base.read_json(folder / 'ready.json')
    assert ready['collection_hashes'] == {k: v['sha256'] for k, v in config['collections'].items()}
    for method in ['sampled', 'greedy']:
        records = base.read_json(folder / f'{method}-records.json')
        keys = {(r['item_id'], r['told'], r['sample']) for r in records}
        expected = expected_keys if method == 'sampled' else {(i, t, 0) for i, t, s in expected_keys}
        assert len(records) == len(expected) and keys == expected
        assert all(r['status'] == 'complete' and r['letter'] in 'ABCD' and r['detected'] == (r['letter'] == 'A') for r in records)
        values = base.metrics.collect(records, pairs)
        points = base.metrics.point_estimates(values, pairs)
        saved = base.read_json(folder / f'{method}-metrics.json')
        assert base.digest(points) == base.digest(saved['point_estimates'])
        collected[(method, scope)] = values
        row = report_row('GLiDE-9B', scope, method, records, points, saved['intervals'])
        row['hierarchical_judgments'] = 0
        row['model_requests'] = 150
        rows.append(row)

# Samples share identities, but GLiDE draws use one vector rather than four analyses.
differences = {scope: base.metrics.paired_difference(collected[('sampled', scope)], collected[('qwen', scope)], pairs)
               for scope in runs}

# Reconstruct scope boundaries from last completions in each Qwen session.
# The shared worker pool overlaps scope boundaries, so these are phase estimates.
parse = datetime.fromisoformat
phases = []
for session in manifest['sessions']:
    per = {scope: [r for r in records if session['started_at'] <= r['finished_at'] <= session['finished_at']]
           for scope, records in qrecords.items()}
    if not any(per.values()):
        continue
    assert sum(map(len, per.values())) == session['units_run']
    previous = session['started_at']
    for scope in ['action', 'cot', 'all']:
        group = per[scope]
        end = max(r['finished_at'] for r in group)
        assert parse(end) > parse(previous)
        phases.append({'job_id': session['compute']['job_id'], 'scope': scope, 'units': len(group),
                       'start_boundary': previous, 'end_boundary': end,
                       'estimated_seconds': (parse(end) - parse(previous)).total_seconds(),
                       'finished_before_start_boundary': sum(r['finished_at'] < previous for r in group)})
        previous = end
compute = compute_by_monitor(manifest, all_records)['monitors']['qwen3-32b']
report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'same_75_rollouts_and_labels': True,
          'same_600_sampled_judgment_keys_per_scope': True, 'framework_commit': config['framework_commit'],
          'qwen_source': str(qdir), 'qwen_source_sha256': {f: base.file_hash(qdir / f) for f in ['manifest.json', 'items.jsonl', 'metrics.json']},
          'qwen_settings': manifest['monitors']['qwen3-32b'], 'qwen_concurrency': manifest['spec']['options']['concurrency'],
          'rows': rows, 'paired_sampled_gmean2_differences_glide_minus_qwen': differences,
          'timing': {'qwen_recorded_sessions': compute, 'qwen_approximate_phases': phases,
                     'qwen_approximate_seconds_by_scope': {s: sum(p['estimated_seconds'] for p in phases if p['scope'] == s) for s in qcells},
                     'glide_gpu_job_seconds': {'action': 304, 'cot': 27*60+13+39*60},
                     'glide_hardware': 'One RTX PRO 6000 Blackwell',
                     'glide_decoding_methods_share_inference': True,
                     'caveat': 'Qwen phases are approximate because scopes overlap in a 32-worker pool; total is recorded evaluation-session time. GLiDE uses scheduler durations, including startup and the failed first CoT attempt. Hardware, concurrency, prompting, number of model calls and hierarchy differ; these are observed system runtimes, not model speed benchmarks.'},
          'glide_combined_status': 'not evaluated',
          'limitations': ['Qwen generates four separate thinking analyses; GLiDE samples four labels from one vector.',
                          'GLiDE uses the adapted decision prompt and direct full inputs; Qwen uses the original prompt and hierarchy when required.',
                          'Highest-probability GLiDE answers are a secondary decision rule; no corresponding Qwen greedy run exists.',
                          'Metrics pool both target objectives. Clean-control false alarms exclude cross-objective and own-failure groups.',
                          'Paired bootstrap comparisons are exploratory and cover the same three tasks, not generalization to new tasks.']}
out = root / 'mihai/decision_models/comparisons/glide-vs-qwen32b-20261115'
base.write_json(out / 'comparison.json', report)
print(json.dumps({'rows': [{k:r[k] for k in ['model','scope','method','detection','clean_false_alarm','gmean2','positive_and_clean_accuracy','hierarchical_judgments','model_requests']} for r in rows],
                  'differences': differences, 'timing': report['timing']}))
