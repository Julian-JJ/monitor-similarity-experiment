"""Run Jev on the exact prepared GLiDE inputs; keep outputs in a separate folder.

prepare and score are offline. full/chunks/summaries require an environment key.
One call yields probabilities; sampled labels are drawn locally without extra calls.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time

from client import MODEL, JevError, decide, validate

HERE = Path(__file__).resolve().parent


def setup(config):
    package = Path(config['glide_package'])
    import hashlib
    if hashlib.sha256((package / 'source-manifest.json').read_bytes()).hexdigest() != config['glide_manifest_sha256']:
        raise ValueError('Wrong frozen comparison source')
    sys.path.insert(0, str(package))
    import run_variants as variants
    source = json.loads((package / 'config.json').read_text())
    base = variants.setup(source)  # Verifies the entire frozen framework inventory.
    cases = variants.inputs(base, source, Path(source['output_dir']))
    if base.file_hash(Path(source['output_dir']) / 'inputs.json') != config['inputs_sha256']:
        raise ValueError('Inputs differ from the GLiDE comparison')
    if len(cases) != 450 or len({(c['scope'], c['item_id'], c['told']) for c in cases}) != 450:
        raise ValueError('Expected 450 unique cases: 75 rollouts x 2 objectives x 3 scopes')
    for case in cases:
        if base.digest({k: v for k, v in case.items() if k != 'sha256'}) != case['sha256']:
            raise ValueError('Prepared case content hash is invalid')
    return base, source, cases


def fingerprints(base, config):
    return {'config_sha256': base.digest(config),
            'code_sha256': {n: base.file_hash(HERE / n) for n in ['run_jev.py', 'client.py']}}


def prepare(base, config, source, cases, out):
    ready = {**fingerprints(base, config), 'model': MODEL, 'api_calls_made': 0,
             'rollouts': 75, 'cases': len(cases), 'chunks': sum(len(c['chunks']) for c in cases),
             'scopes': {}, 'qwen_summary_cases_ready': 0}
    for scope in ['action', 'cot', 'all']:
        selected = [c for c in cases if c['scope'] == scope]
        ready['scopes'][scope] = {'cases': len(selected), 'chunks': sum(len(c['chunks']) for c in selected),
                                 'max_glide_tokens_reference_only': max(c['full_tokens'] for c in selected)}
    ready['qwen_summary_cases_ready'] = sum(summary_input(base, source, c) is not None for c in cases)
    ready['maximum_api_calls'] = 2 * len(cases) + ready['chunks']
    ready['jev_token_counts'] = 'Unknown until API response; GLiDE counts are not Jev counts'
    path = out / 'ready.json'
    if path.exists():
        old = base.read_json(path)
        if any(old[k] != v for k, v in fingerprints(base, config).items()):
            raise ValueError('Preparation already exists for different code/config; use a new run directory')
        print(json.dumps(old)); return
    base.write_json(path, ready)
    print(json.dumps(ready), flush=True)


def summary_input(base, source, case):
    from prompts import summary_request
    texts = []
    identity = {'config': base.digest(source), 'case': case['sha256']}
    for part in case['chunks']:
        path = Path(source['output_dir']) / 'qwen' / f"{case['index']:03d}" / 'summaries' / f"{part['index']:03d}.json"
        if not path.exists(): return None
        row = base.read_json(path)
        expected = base.digest({**identity, 'summary_prompt': part['summary_prompt']})
        if row['identity_sha256'] != expected: raise ValueError('Qwen summary identity mismatch')
        if row['status'] != 'complete': return None
        if not isinstance(row.get('text'), str) or not row['text'].strip():
            raise ValueError('Empty Qwen summary')
        texts.append(row['text'])
    return summary_request(case['planned']['main_task'], case['planned']['objective'], texts,
                           case['full_request']['questions']['verdict']['criteria'])


def request_identity(base, config, case, request, long_context):
    return base.digest({'config': base.digest(config), 'case': case['sha256'],
                        'request': request, 'long_context': long_context})


def saved_call(base, config, case, request, path, long_context, call=decide):
    identity = request_identity(base, config, case, request, long_context)
    if path.exists():
        result = result_at(base, path, identity)
        if result['status'] != 'complete':
            raise RuntimeError('A failed/interrupted API attempt needs review; refusing to send it twice')
        return result
    # Persist an intent before HTTP: a crash must not silently repeat a paid call.
    result = {'status': 'attempting', 'identity_sha256': identity}
    base.write_json(path, result)
    started = time.monotonic()
    try:
        answer = call(request, long_context, config['timeout_seconds'])
        distribution = base.sampling_distribution(answer['probabilities'], 0.6, 0.9)
        draws = base.draw_answers(distribution, f"{case['item_id']}:{case['told']}", 0, 4)
        result.update(status='complete', **answer, sampling_probabilities=distribution, draws=draws)
    except JevError as error:
        result.update(status='failed', error=str(error), http_status=error.http_status)
    result['seconds'] = time.monotonic() - started
    result['result_sha256'] = base.digest(result)
    base.write_json(path, result)
    # Stop on errors instead of repeatedly charging, hitting rate limits, or changing inputs.
    if result['status'] != 'complete': raise RuntimeError('API attempt failed; see its saved status')
    return result


def run(base, config, source, cases, out, stage):
    if not os.environ.get('TYPESAFE_API_KEY'):
        raise RuntimeError('Set TYPESAFE_API_KEY privately before running; no API call was made')
    for case in cases:
        directory = out / stage / f"{case['index']:03d}"
        if stage == 'chunks':
            requests = [(f"{p['index']:03d}.json", p['glide_request']) for p in case['chunks']]
        else:
            req = case['full_request'] if stage == 'full' else summary_input(base, source, case)
            if req is None:
                base.write_json(directory / 'blocked.json', {'status': 'blocked',
                                'reason': 'Not all matching Qwen summaries are complete'})
                continue
            requests = [('result.json', req)]
        long_context = stage == 'full' and case['scope'] in ['cot', 'all']
        for name, req in requests:
            path = directory / name
            was_saved = path.exists()
            saved_call(base, config, case, req, path, long_context)
            if not was_saved: time.sleep(config['request_spacing_seconds'])
        print(json.dumps({'stage': stage, 'case': case['index'], 'status': 'complete'}), flush=True)


def result_at(base, path, identity):
    if path.exists():
        row = base.read_json(path)
        if row['identity_sha256'] != identity: raise ValueError('Cached request identity changed')
        if row['status'] == 'attempting': return {**row, 'status': 'interrupted'}
        if row['result_sha256'] != base.digest({k: v for k, v in row.items() if k != 'result_sha256'}):
            raise ValueError('Saved result content changed')
        if row['status'] == 'complete':
            if any(row[k] != v for k, v in validate(row['response']).items()):
                raise ValueError('Stored decision differs from the Jev response')
        return row
    blocked = path.parent / 'blocked.json'
    return base.read_json(blocked) if blocked.exists() else {'status': 'not_started'}


def aggregate_case(base, config, case, out, rule):
    from aggregation import aggregate
    rows = [{**result_at(base, out / 'chunks' / f"{case['index']:03d}" / f"{p['index']:03d}.json",
                        request_identity(base, config, case, p['glide_request'], False)),
             'index': p['index']} for p in case['chunks']]
    states = {r['status'] for r in rows}
    if states == {'complete'}: return aggregate(rows, len(rows), 0.5)[rule]
    status = next(s for s in ['failed', 'interrupted', 'blocked', 'not_started'] if s in states)
    return {'status': status, 'detected': None, 'complete_chunks': sum(r['status'] == 'complete' for r in rows)}


def score(base, config, source, cases, out):
    _, items = base.load_items(source)
    pairs = {p.key: p for p in base.make_pairs(items)}
    report = {}
    for scope in ['action', 'cot', 'all']:
        for variant in ['full-greedy', 'full-sampled', 'max', 'mean', 'summaries']:
            records = []
            for c in [c for c in cases if c['scope'] == scope]:
                if variant in ['max', 'mean']: row = aggregate_case(base, config, c, out, variant)
                else:
                    stage = 'full' if variant.startswith('full') else 'summaries'
                    path = out / stage / f"{c['index']:03d}" / 'result.json'
                    req = c['full_request'] if stage == 'full' else summary_input(base, source, c)
                    identity = request_identity(base, config, c, req, stage == 'full' and scope in ['cot', 'all'])
                    row = result_at(base, path, identity)
                    if row['status'] == 'complete':
                        distribution = base.sampling_distribution(row['probabilities'], 0.6, 0.9)
                        draws = base.draw_answers(distribution, f"{c['item_id']}:{c['told']}", 0, 4)
                        if row['draws'] != draws or row['sampling_probabilities'] != distribution:
                            raise ValueError('Stored sampled answers differ from the declared rule')
                n = 4 if variant == 'full-sampled' else 1
                for sample in range(n):
                    letter = row.get('draws', [{}] * 4)[sample].get('letter') if n == 4 else row.get('letter')
                    detected = (letter == 'A' if n == 4 else row.get('detected')) if row['status'] == 'complete' else None
                    records.append({'item_id': c['item_id'], 'told': c['told'], 'sample': sample,
                                    'status': row['status'], 'letter': letter, 'detected': detected,
                                    'score_a': row.get('score_a', row.get('probabilities', {}).get('A'))})
            name = f'{scope}-{variant}'
            collected = base.metrics.collect(records, pairs)
            base.write_json(out / 'scores' / f'{name}-records.json', records)
            base.write_json(out / 'scores' / f'{name}-metrics.json', {
                'point_estimates': base.metrics.point_estimates(collected, pairs),
                'intervals': base.metrics.bootstrap_intervals(collected, pairs, n=2000, seed=0)})
            report[name] = dict(Counter(r['status'] for r in records))
    base.write_json(out / 'summary.json', report)
    print(json.dumps(report), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'full', 'chunks', 'summaries', 'score'])
    parser.add_argument('config', type=Path)
    parser.add_argument('--smoke', action='store_true', help='Shortest and longest real case in each scope')
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    base, source, cases = setup(config)
    out = Path(config['output_dir']); out.mkdir(parents=True, exist_ok=True)
    # File lock prevents two invocations from sending the same requests concurrently.
    with base.lock(out / 'jev.lock'):
        if args.stage == 'prepare': prepare(base, config, source, cases, out); return
        ready = base.read_json(out / 'ready.json')
        if any(ready[k] != v for k, v in fingerprints(base, config).items()):
            raise ValueError('Code/config changed after preparation; use a new run directory')
        if args.smoke:
            if args.stage == 'score': raise ValueError('Score always uses the full denominator')
            selected = set()
            for scope in ['action', 'cot', 'all']:
                group = [c for c in cases if c['scope'] == scope]
                selected.update([min(group, key=lambda c: c['full_tokens'])['index'],
                                 max(group, key=lambda c: c['full_tokens'])['index']])
            cases = [c for c in cases if c['index'] in selected]
        started = time.monotonic()
        if args.stage == 'score': score(base, config, source, cases, out)
        else: run(base, config, source, cases, out, args.stage)
        base.write_json(out / f'session-{args.stage}-{time.time_ns()}.json', {
            'stage': args.stage, 'smoke': args.smoke, 'wall_seconds': time.monotonic() - started,
            'hosting': 'TypeSafe API; server GPU and memory are not exposed'})


if __name__ == '__main__':
    main()
