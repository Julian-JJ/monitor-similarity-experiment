"""Run on the cluster: verify saved full-input responses and export only probabilities.

No inference, API calls, credentials, transcripts or reasoning are needed in the export.
Run with the existing research Python and -B; stdout is the compact JSON export.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

PROJECT = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73')


def read(path):
    return json.loads(path.read_text())


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def verify_release(path, expected):
    assert file_hash(path / 'source-manifest.json') == expected
    files = read(path / 'source-manifest.json')['files']
    assert {str(p.relative_to(path)) for p in path.rglob('*') if p.is_file()} == set(files) | {'source-manifest.json'}
    assert all(file_hash(path / name) == sha for name, sha in files.items())


def cases(path, expected_hash):
    """Read one top-level object at a time from the existing indented JSON array."""
    sha = hashlib.sha256()
    lines = None
    with path.open('rb') as stream:
        for line in stream:
            sha.update(line)
            if line == b'  {\n':
                lines = []
            if lines is not None:
                lines.append(line)
            if line in (b'  },\n', b'  }\n'):
                yield json.loads(b''.join(lines).decode().rstrip().removesuffix(','))
                lines = None
    assert sha.hexdigest() == expected_hash, 'Prepared input file changed'


def main():
    package = PROJECT / 'releases/decision-variants-d98ee84c398bee9b'
    jev_package = PROJECT / 'releases/jev-variants-4090274c5245883d'
    verify_release(package, 'd98ee84c398bee9b90f66132b15a8c5fd53476d97534a0d5a1f9569cbde0a616')
    verify_release(jev_package, '4090274c5245883d97f411c3a33c0fb9f4ae75f58fb0a7a16c065314530c67ff')
    config, jev_config = read(package / 'config.json'), read(jev_package / 'config.json')
    framework = Path(config['framework_source'])
    verify_release(framework, config['framework_manifest_sha256'])
    out, jev_out = Path(config['output_dir']), Path(jev_config['output_dir'])
    ready, jev_ready = read(out / 'ready.json'), read(jev_out / 'ready.json')
    assert ready['config_sha256'] == digest(config)
    assert jev_ready['config_sha256'] == digest(jev_config)
    assert jev_config['inputs_sha256'] == ready['inputs_sha256']
    assert jev_config['glide_package'] == str(package)
    assert config['model_revision'] == 'ab54df5acba0eebf7df45560ffdaacd64e32df3b'
    rows, reused = [], {}

    def append(model, scope, case, path, row):
        assert row['status'] == 'complete'
        answer = row['response']['answers']['verdict']
        probabilities = answer['probabilities']
        assert answer['type'] == 'choice' and set(probabilities) == set('ABCD')
        assert all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1
                   for p in probabilities.values())
        assert math.isclose(sum(probabilities.values()), 1, abs_tol=1e-5)
        winner = max('ABCD', key=probabilities.get)
        assert probabilities[answer['choice']] == probabilities[winner]
        assert row.get('letter', row.get('greedy_letter')) == winner
        if 'probabilities' in row:
            assert row['probabilities'] == probabilities
        if model == 'jev':
            assert row['response']['model'] == 'jev-1.14.0'
        else:
            tokens = case.get('prompt_tokens', case.get('full_tokens'))
            assert row['response']['usage'] == {'input_tokens': tokens, 'output_tokens': 0}
        rows.append({'model': model, 'scope': scope, 'item_id': case['item_id'],
                     'told': case['told'], 'status': 'complete', 'probabilities': probabilities,
                     'original_letter': winner, 'source_path': str(path),
                     'source_sha256': file_hash(path), 'request_sha256': digest(case.get('request', case.get('full_request')))})

    for scope, folder in config['reuse'].items():
        folder = Path(folder)
        for name, sha in ready['reuse_hashes'][scope].items():
            assert file_hash(folder / name) == sha
        old_ready = read(folder / 'ready.json')
        assert old_ready['collection_hashes'] == ready['collection_hashes']
        mapping = {}
        for index, case in enumerate(cases(folder / 'inputs.json', old_ready['inputs_sha256'])):
            assert digest(case['request']) == case['request_sha256']
            path = folder / 'pairs' / f'{index:03d}.json'
            row = read(path)
            assert row['request_sha256'] == case['request_sha256']
            assert row['config_sha256'] == old_ready['config_sha256']
            assert (row['item_id'], row['told']) == (case['item_id'], case['told'])
            append('glide', scope, case, path, row)
            mapping[(case['item_id'], case['told'])] = case['request_sha256']
        assert len(mapping) == 150
        reused[scope] = mapping

    for index, case in enumerate(cases(out / 'inputs.json', ready['inputs_sha256'])):
        assert case['index'] == index
        assert digest({k: v for k, v in case.items() if k != 'sha256'}) == case['sha256']
        scope = case['scope']
        if scope in reused:
            assert digest(case['full_request']) == reused[scope][(case['item_id'], case['told'])]
        else:
            path = out / 'glide-full' / f'{index:03d}' / 'result.json'
            row = read(path)
            assert row['identity_sha256'] == digest({'config': digest(config), 'case': case['sha256'],
                                                     'request': case['full_request']})
            append('glide', scope, case, path, row)
        path = jev_out / 'full' / f'{index:03d}' / 'result.json'
        row = read(path)
        assert row['identity_sha256'] == digest({'config': digest(jev_config), 'case': case['sha256'],
                    'request': case['full_request'], 'long_context': scope in ['cot', 'all']})
        assert row['result_sha256'] == digest({k: v for k, v in row.items() if k != 'result_sha256'})
        append('jev', scope, case, path, row)
    assert len(rows) == 900
    assert len({(r['model'], r['scope'], r['item_id'], r['told']) for r in rows}) == 900
    assert Counter((r['model'], r['scope']) for r in rows) == {
        (m, s): 150 for m in ['glide', 'jev'] for s in ['action', 'cot', 'all']}
    print(json.dumps({'audit_passed': True, 'checked_utc': datetime.now(timezone.utc).isoformat(),
        'inference_calls': 0, 'collection_hashes': ready['collection_hashes'],
        'inputs_sha256': ready['inputs_sha256'],
        'metrics_source_sha256': file_hash(framework / 'monitor_experiment/metrics.py'),
        'config_sha256': {'glide': digest(config), 'jev': digest(jev_config)},
        'rows': sorted(rows, key=lambda r: (r['model'], r['scope'], r['item_id'], r['told']))}, indent=2))


if __name__ == '__main__':
    main()
