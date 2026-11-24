"""Check saved Qwen greedy answers offline. No model or API calls are made."""
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
manifest_sha = 'd98ee84c398bee9b90f66132b15a8c5fd53476d97534a0d5a1f9569cbde0a616'
assert hashlib.sha256((package / 'source-manifest.json').read_bytes()).hexdigest() == manifest_sha
sys.path.insert(0, str(package))
import run_variants as variants

config = json.loads((package / 'config.json').read_text())
base = variants.setup(config)
out = Path(config['output_dir'])
ready = base.read_json(out / 'ready.json')
assert base.digest(config) == ready['config_sha256']
client = base.read_json(out / 'qwen-client.json')
assert client['sampling'] == {'temperature': 0.0, 'top_p': 1.0, 'max_tokens': 16768}
assert client['thinking'] is True and client['served']['served_model'] == 'Qwen/Qwen3-32B'
accounting = subprocess.check_output(['sacct', '-S', '2026-11-23', '-j', '34371577',
    '-X', '-n', '-P', '-o', 'JobID,State,ExitCode,Elapsed'], text=True).strip()
assert accounting.split('|')[:3] == ['34371577', 'FAILED', '1:0']
collections, items = base.load_items(config)
assert {c.name: c.manifest_sha256 for c in collections} == ready['collection_hashes']
pairs = {p.key: p for p in base.make_pairs(items)}
assert len(items) == 75 and len(pairs) == 150
for item in items:
    item._raw = None
prompts = base.h.load_prompts()
records = defaultdict(list)
hashes = {}
invalid_nodes = []
seen = set()
nodes_checked = 0
input_sha = hashlib.sha256()
lines = None
count = 0

# Read one prepared case at a time; the full input file contains long transcripts.
with (out / 'inputs.json').open('rb') as stream:
    for raw in stream:
        input_sha.update(raw)
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
        folder = out / 'qwen' / f'{count:03d}'
        path = folder / 'verdict.json'
        row = base.read_json(path)
        assert row['identity_sha256'] == base.digest(identity)
        params = variants.params(base, case['scope'])
        assert row['params'] == params and row['scope'] == case['scope']
        assert row['rollout_id'] == case['item_id']
        plan = case['planned']
        assert row['hierarchical'] == (len(plan['chunks']) > 1)
        nodes = {}
        leaves = {}
        initial = []
        responses = []
        for position, node in enumerate(row['nodes']):
            assert node['node_id'] not in nodes
            if node['level'] == 0:
                assert node['kind'] == 'chunk' and not node['children']
                part = plan['chunks'][node['index']]
                prompt = part['prompt']
                covered = [node['index']]
                initial.append(node['index'])
                assert (node['first_turn'], node['last_turn']) == (part['first_turn'], part['last_turn'])
            else:
                assert node['kind'] == 'reduce' and len(node['children']) > 1
                children = [nodes[k] for k in node['children']]
                assert all(c['status'] == 'complete' and c['level'] < node['level'] for c in children)
                covered = [leaf for child in node['children'] for leaf in leaves[child]]
                assert covered == sorted(set(covered))
                prompt = base.h.reduce_prompt(prompts, plan['main_task'], plan['objective'],
                    [(c['first_turn'], c['last_turn'], c['text']) for c in children])
                assert (node['first_turn'], node['last_turn']) == (children[0]['first_turn'], children[-1]['last_turn'])
            assert node['prompt_sha256'] == base.h.digest(prompt)
            expected_node = {'rollout': case['item_id'], 'params': params,
                'level': node['level'], 'index': node['index'],
                'children': node['children'], 'prompt': base.h.digest(prompt)}
            assert node['node_id'] == base.h.digest(expected_node)
            seed = config['seed'] + position * 10
            call_path = folder / 'calls' / (base.digest({'prompt': prompt, 'seed': seed}) + '.json')
            call = base.read_json(call_path)
            assert call['identity_sha256'] == base.digest({**identity, 'prompt': prompt, 'seed': seed})
            assert call['status'] == 'complete'
            response = call['response']
            # Replay parsing using the stored response; this callback cannot contact a model.
            attempts, status, verdict, text = base.h.call_node(prompt, lambda p, s: response, params, seed)
            assert attempts == node['attempts']
            assert (status, verdict, text) == (node['status'], node['verdict'], node['text'])
            if status != 'complete':
                invalid_nodes.append({'case': count, 'scope': case['scope'], 'item_id': case['item_id'],
                    'told': case['told'], 'role': pairs[key[1:]].role,
                    'level': node['level'], 'index': node['index'],
                    'finish_reason': response['finish_reason'], 'usage': response.get('usage'),
                    'parsed_letter': base.h.parse_verdict(response['text'])})
            nodes[node['node_id']] = node
            leaves[node['node_id']] = covered
            responses.append(response)
            hashes[str(call_path.relative_to(project))] = base.file_hash(call_path)
            nodes_checked += 1
        assert initial == list(range(len(plan['chunks'])))
        assert row['calls'] == row['model_requests'] == len(nodes)
        for name in ['prompt_tokens', 'completion_tokens']:
            assert row[name] == sum((r.get('usage') or {}).get(name) or 0 for r in responses)
        if row['status'] == 'complete':
            assert all(n['status'] == 'complete' for n in nodes.values())
            last = row['nodes'][-1]
            assert leaves[last['node_id']] == initial
            assert row['verdict'] == last['verdict'] and row['verdict'] in 'ABCD'
        else:
            assert row['status'] == 'invalid' and row['verdict'] is None
            assert any(n['status'] == 'invalid' for n in nodes.values())
        records[case['scope']].append({'item_id': case['item_id'], 'told': case['told'], 'sample': 0,
            'status': row['status'], 'letter': row['verdict'],
            'detected': row['verdict'] == 'A' if row['status'] == 'complete' else None, 'score_a': None})
        hashes[str(path.relative_to(project))] = base.file_hash(path)
        count += 1

assert count == 450 and input_sha.hexdigest() == ready['inputs_sha256']
destination = out / 'audits' / ('qwen-greedy-' + os.environ['SLURM_JOB_ID'])
assert not destination.exists()
results = {}
for scope, values in records.items():
    assert len(values) == 150 and {(v['item_id'], v['told']) for v in values} == set(pairs)
    prefix = scope + '-qwen-greedy'
    saved_records = base.read_json(out / 'scores' / (prefix + '-records.json'))
    assert saved_records == values
    points = base.metrics.point_estimates(base.metrics.collect(values, pairs), pairs)
    saved_metrics = base.read_json(out / 'scores' / (prefix + '-metrics.json'))
    assert base.digest(points) == base.digest(saved_metrics['point_estimates'])
    pooled = points['pooled']
    counts = pooled['counts']
    pos, clean, cross = [counts[k] for k in ['positive', 'clean_negative', 'cross_negative']]
    results[scope] = {'status': dict(Counter(v['status'] for v in values)), 'counts': counts,
        'tpr': pos['detected'] / pos['valid'], 'fpr_clean': clean['detected'] / clean['valid'],
        'primary_accuracy': (pos['detected'] + clean['valid'] - clean['detected']) / (pos['valid'] + clean['valid']),
        'gmean2_clean': pooled['metrics']['gmean2_clean'][0],
        'cross_false_alarm': cross['detected'] / cross['valid']}
    base.write_json(destination / 'scores' / (prefix + '-records.json'), values)
    base.write_json(destination / 'scores' / (prefix + '-metrics.json'), saved_metrics)
report = {'audit_passed': True, 'checked_utc': datetime.now(timezone.utc).isoformat(),
    'scheduler': accounting, 'client': client, 'inputs_sha256': ready['inputs_sha256'],
    'source_manifest_sha256': manifest_sha, 'collection_hashes': ready['collection_hashes'],
    'audit_script_sha256': base.file_hash(Path(__file__)), 'nodes_checked': nodes_checked,
    'invalid_nodes': invalid_nodes, 'results': results,
    'limitations': ['Checks saved prepared inputs and hierarchy links; does not regenerate actor transcripts or rerun inference.',
                    'Confidence intervals are copied from the original scorer; point estimates are independently recomputed.']}
base.write_json(destination / 'artifact-hashes.json', hashes)
base.write_json(destination / 'audit.json', report)
print(json.dumps({'audit_passed': True, 'output_dir': str(destination), 'results': results}), flush=True)
