"""Recompute both Qwen baselines from saved decisions; print no transcript text."""
import json
from pathlib import Path
import sys

project = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')
source = project / 'releases/glide-cot-20261115-c8f6c4e8'
sys.path.insert(0, str(source / 'mihai/decision_models'))
import run_evaluation as base

base.verify_source()
config = base.read_json(source / 'mihai/decision_models/evaluation.json')
collections, items = base.load_items(config)
pairs = {p.key: p for p in base.make_pairs(items)}
folder = Path('/nfs/roberts/project/cpsc4880/cpsc4880_as4833/runs/baseline')
manifest = base.read_json(folder / 'manifest.json')
stored = base.read_json(folder / 'metrics.json')
records = [json.loads(line) for line in (folder / 'items.jsonl').read_text().splitlines()]
assert set(manifest['item_ids']) == {i.item_id for i in items}
assert {k: v['manifest_sha256'] for k, v in manifest['rollout_sets'].items()} == {c.name: c.manifest_sha256 for c in collections}
expected = {(i.item_id, told, s) for i in items for told in ['malicious', 'benign'] for s in range(4)}
report = {}
for cell in stored['cells']:
    selected = [r for r in records if r['cell_id'] == cell['cell_id']]
    assert len(selected) == 600 and {(r['item_id'], r['told'], r['sample']) for r in selected} == expected
    assert all(r['status'] == 'complete' and r['letter'] in 'ABCD' and r['detected'] == (r['letter'] == 'A') for r in selected)
    points = base.metrics.point_estimates(base.metrics.collect(selected, pairs), pairs)
    for told in ['malicious', 'benign', 'pooled']:
        assert points[told]['counts'] == cell['results'][told]['counts']
        for metric, (value, reason) in points[told]['metrics'].items():
            assert value == cell['results'][told]['metrics'][metric]['value']
    report[cell['label']['monitor'] + '-' + cell['label']['scope']] = {'complete': len(selected), 'counts_and_metrics_match': True}
report['source_hashes'] = {n: base.file_hash(folder / n) for n in ['items.jsonl', 'metrics.json', 'manifest.json']}
base.write_json(project / 'logs/baseline-audit-20261123.json', report)
print(json.dumps(report), flush=True)
