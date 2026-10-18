"""Summarize failed requests using metadata and repetition counts only."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path('/nfs/roberts/project/cpsc4880/cpsc4880_mae73/test_rollouts_2/runs/29910578')
rows = []
for path in sorted((ROOT/'raw').glob('*.json')):
    record = json.loads(path.read_text())
    if record['status'] != 'execution_error':
        continue
    response = record.get('raw_response') or {}
    choice = (response.get('choices') or [{}])[0]
    message = choice.get('message') or {}
    reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
    words = re.findall(r'\S+', reasoning)
    windows = Counter(tuple(words[i:i+8]) for i in range(max(0, len(words)-7)))
    row = {'case_id': record['case']['case_id'], 'error_type': record.get('error_type'),
           'finish_reason': choice.get('finish_reason'), 'usage': record.get('usage'),
           'elapsed_seconds': record.get('elapsed_seconds'),
           'final_answer_nonempty': bool((message.get('content') or '').strip()),
           'reasoning_characters': len(reasoning),
           'repetition_metrics': {'whitespace_words': len(words),
                                  'unique_8_word_windows': len(windows),
                                  'largest_8_word_window_count': max(windows.values(), default=0)},
           'raw_path': str(path)}
    rows.append(row)
print(json.dumps({'job_id': 29910578, 'failed_requests': rows,
                  'note': 'No reasoning text or window contents exported. Repetition metrics alone do not prove degeneration.'}))
