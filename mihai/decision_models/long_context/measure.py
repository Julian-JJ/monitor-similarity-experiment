"""Run increasing lengths in separate GPU processes; stop on a resource failure."""
import argparse
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import sys
import time

from prepare import setup


def measure_level(config, target):
    base = setup(config)
    out = Path(config['output_dir'])
    ready = base.read_json(out / 'ready.json')
    assert ready['config_sha256'] == base.digest(config)
    level = next(row for row in ready['levels'] if row['target'] == target)
    assert base.file_hash(out / level['file']) == level['sha256']
    cases = base.read_json(out / level['file'])
    sys.path.insert(0, config['model_dir'])
    import torch
    from glide import Glide

    torch.cuda.synchronize()  # Wait for GPU work; otherwise timings can stop too early.
    started = time.perf_counter()
    model = Glide.from_pretrained(config['model_dir'], vision=False, max_len=target + 8)
    torch.cuda.synchronize()
    info = {'target': target, 'load_seconds': time.perf_counter() - started,
            'gpu': torch.cuda.get_device_name(), 'gpu_total_bytes': torch.cuda.get_device_properties(0).total_memory,
            'torch': torch.__version__, 'cuda': torch.version.cuda, 'pid': os.getpid(),
            'job_id': os.environ.get('SLURM_JOB_ID'), 'model_allocated_bytes': torch.cuda.memory_allocated(),
            'model_reserved_bytes': torch.cuda.memory_reserved(), 'status': 'running'}
    base.write_json(out / f'level-{target}.json', info)
    assert model.temperature == 1.0
    for case in cases:
        assert base.digest(case['request']) == case['request_sha256']
        for repeat in range(case['repeats']):
            path = out / 'measurements' / f"{target}-{case['id']}-{repeat}.json"
            if path.exists():
                raise RuntimeError('A measurement already exists; do not overwrite a pilot')
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()  # Reset the per-call maximum, not the model weights.
            before = torch.cuda.memory_allocated()
            record = {k: v for k, v in case.items() if k not in ['request', 'repeats']}
            record.update(target=target, repeat=repeat, status='running',
                          started_at=time.time(), allocated_before_bytes=before)
            base.write_json(out / 'current.json', {k: record[k] for k in ['target', 'id', 'repeat', 'started_at']})
            started = time.perf_counter()
            try:
                response = model.decide(**case['request'])  # ** supplies state= and questions=.
                torch.cuda.synchronize()
                seconds = time.perf_counter() - started
                assert response['usage']['input_tokens'] == case['prompt_tokens']
                answer = response['answers']['verdict']
                distribution = base.sampling_distribution(answer['probabilities'], 0.6, 0.9)
                assert answer['choice'] == max('ABCD', key=lambda x: answer['probabilities'][x])
                record.update(status='complete', seconds=seconds, response=response,
                    sampled_answers=base.draw_answers(distribution, f"{target}:{case['id']}", 0, 4),
                    correct=None if case['expected_detected'] is None else
                            ((answer['choice'] == 'A') == case['expected_detected']))
            except Exception as error:
                record.update(status='failed', seconds=time.perf_counter() - started,
                              error_type=type(error).__name__, error=str(error)[:700])
            record.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                          peak_reserved_bytes=torch.cuda.max_memory_reserved())
            record['incremental_peak_bytes'] = record['peak_allocated_bytes'] - before
            base.write_json(path, record)
            print(json.dumps({k: record[k] for k in ['target', 'id', 'repeat', 'status', 'seconds', 'peak_allocated_bytes']}), flush=True)
            if record['status'] != 'complete':
                info.update(status='failed', error_type=record['error_type'])
                base.write_json(out / f'level-{target}.json', info)
                return 1
    info['status'] = 'complete'
    base.write_json(out / f'level-{target}.json', info)
    return 0


def run(config, config_path):
    base = setup(config)
    out = Path(config['output_dir'])
    ready = base.read_json(out / 'ready.json')
    assert ready['config_sha256'] == base.digest(config)
    assert ready['source_manifest_sha256'] == base.file_hash(Path(__file__).with_name('source-manifest.json'))
    stages = []
    for level in ready['levels']:
        target = level['target']
        if (out / f'level-{target}.json').exists():
            raise RuntimeError('Pilot measurements already exist; reconcile before another run')
        command = [sys.executable, '-B', __file__, str(config_path), '--level', str(target)]
        started = time.perf_counter()
        # A new process releases GPU memory and isolates each length's measurements.
        child = subprocess.Popen(command, start_new_session=True)
        try:
            code = child.wait(timeout=config['seconds_per_level'])
            status = 'complete' if code == 0 else 'failed'
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)  # Stop only this pilot's process group.
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            code, status = child.returncode, 'timeout'
        stage = {'target': target, 'status': status, 'exit_code': code,
                 'wall_seconds_including_load': time.perf_counter() - started}
        stages.append(stage)
        base.write_json(out / 'progress.json', stages)
        if status != 'complete':
            break
    summary = {'levels': stages, 'not_started': [r['target'] for r in ready['levels'][len(stages):]],
               'stopped_at_limit': bool(stages and stages[-1]['status'] != 'complete'), 'measurements': []}
    for stage in stages:
        target = stage['target']
        rows = [base.read_json(p) for p in sorted((out / 'measurements').glob(f'{target}-*.json'))]
        real = sorted([r for r in rows if r['kind'] == 'real_prefix' and r['status'] == 'complete'], key=lambda r: r['repeat'])
        synthetic = [r for r in rows if r['kind'] == 'synthetic_control' and r['status'] == 'complete']
        summary['measurements'].append({'target': target, 'status': stage['status'],
            'real_prompt_tokens': real[0]['prompt_tokens'] if real else None,
            'real_is_full_transcript': real[0]['full_transcript'] if real else False,
            'first_call_seconds': real[0]['seconds'] if real else None,
            'warm_mean_seconds': statistics.mean(r['seconds'] for r in real[1:]) if len(real) > 1 else None,
            'peak_allocated_bytes': max((r['peak_allocated_bytes'] for r in rows), default=None),
            'peak_reserved_bytes': max((r['peak_reserved_bytes'] for r in rows), default=None),
            'real_choices': [r['response']['answers']['verdict']['choice'] for r in real],
            'synthetic': [{'id': r['id'], 'correct': r['correct'], 'choice': r['response']['answers']['verdict']['choice'],
                           'p_A': r['response']['answers']['verdict']['probabilities']['A']} for r in synthetic],
            'failures': [{k: r.get(k) for k in ['id', 'repeat', 'error_type', 'error']} for r in rows if r['status'] == 'failed']})
    base.write_json(out / 'summary.json', summary)
    print(json.dumps({'tested_levels': len(stages), 'stopped_at_limit': summary['stopped_at_limit']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--level', type=int)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if args.level is None:
        run(config, args.config)
    else:
        sys.exit(measure_level(config, args.level))
