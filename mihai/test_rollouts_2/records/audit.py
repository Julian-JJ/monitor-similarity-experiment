"""Read-only terminal artifact audit on cluster; exports no reasoning traces."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73/test_rollouts_2')
RELEASE = ROOT/'releases/41e5261de745d76c'
OUT = ROOT/'runs/29910578'
sys.path.insert(0,str(RELEASE))
from runtime.artifacts import digest
from runtime.serving import validate_manifest
from runtime.inference import normalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    release_manifest = json.loads((RELEASE/'release-manifest.json').read_text())
    assert sha(RELEASE/'release-manifest.json') == '41e5261de745d76cf070fa0f6729ed54e6f5d06435341497030d37acbcc15fc3'
    assert {str(p.relative_to(RELEASE)) for p in RELEASE.rglob('*') if p.is_file() and p.name!='release-manifest.json'} == set(release_manifest['files'])
    for name,h in release_manifest['files'].items():
        assert sha(RELEASE/name)==h,name
    config=json.loads((RELEASE/'config.json').read_text())
    cases={c['case_id']:c for c in json.loads((RELEASE/'selection.json').read_text())['cases']}
    manifest=json.loads((OUT/'manifest.json').read_text())
    h=manifest.pop('content_hash');assert digest(manifest)==h;manifest['content_hash']=h
    serving=json.loads((OUT/'serving-manifest.json').read_text())
    download=json.loads((ROOT.parent/'models/qwen3-14b/download-manifest.json').read_text())
    model=validate_manifest(serving,download)
    assert serving['settings']['configuration_hash']==digest(config)
    assert download['revision']==config['model_revision']
    entries=manifest['entries']
    assert len(entries)==20 and {e['case_id'] for e in entries}==set(cases)
    assert {p.stem for p in (OUT/'raw').glob('*.json')}==set(cases)
    assert 'H200' in (OUT/'gpu.csv').read_text()
    rows=[]
    for e in entries:
        case=cases[e['case_id']];path=OUT/'raw'/(e['case_id']+'.json')
        assert Path(e['path'])==path and sha(path)==e['sha256']
        d=json.loads(path.read_text());h=d.pop('content_hash');assert digest(d)==h
        assert d['case']==case and d['case_hash']==digest(case)
        assert d['generation']==config['generation'] and d['provenance']==manifest['provenance']
        assert d['provenance']['served_model_name']==model
        assert d['provenance']['config_sha256']==sha(RELEASE/'config.json')
        assert d['provenance']['selection_sha256']==sha(RELEASE/'selection.json')
        assert d['provenance']['serving_sha256']==sha(OUT/'serving-manifest.json')
        row={k:e[k] for k in ['case_id','family','condition','status','sha256','elapsed_seconds','usage','evaluation']}
        if d['status']=='complete':
            raw=d['raw_response'];assert raw['model']==model
            n=normalize(raw);assert n==d['normalized']
            assert n['finish_reason']=='stop' and n['content'].strip() and n['reasoning'] is not None and not n['tool_calls']
            assert raw['usage']['completion_tokens']<=config['generation']['max_tokens']
            assert raw['usage']['total_tokens']<=config['context_limit']
            row['visible_answer_characters']=len(n['content'])
            row['visible_answer_sha256']=hashlib.sha256(n['content'].encode()).hexdigest()
        else:
            row['error_type']=d.get('error_type')
        rows.append(row)
    assert dict(Counter(r['status'] for r in rows))==manifest['counts']
    return {'verified_at':datetime.now(timezone.utc).isoformat(),'job_id':29910578,
            'artifact_integrity_verified':True,'manifest_sha256':sha(OUT/'manifest.json'),
            'release_sha256':sha(RELEASE/'release-manifest.json'),'serving_sha256':sha(OUT/'serving-manifest.json'),
            'counts':manifest['counts'],'entries':rows,
            'limitations':['20 requests cover 12 fixed problems, not category-wide success estimates.',
                          'Manual main-content grading remains separate from this artifact integrity audit.',
                          'Some standard cases contain a relevant hint or the reference answer; compare controls separately.',
                          'No reasoning traces exported; no MonitorBench monitorability scores computed.']}


if __name__=='__main__':
    print(json.dumps(audit()))
