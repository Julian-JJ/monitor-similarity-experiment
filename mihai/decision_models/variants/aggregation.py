"""Combine chunk probabilities. These binary rules do not invent an A-D verdict."""
import math


def validate_probabilities(probabilities):
    if set(probabilities) != set('ABCD'):
        raise ValueError('Expected exactly the four A-D probabilities')
    values = list(probabilities.values())
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError('Probabilities must be finite and in [0, 1]')
    if not math.isclose(sum(values), 1, abs_tol=1e-5):
        raise ValueError('Probabilities must sum to one')
    return probabilities


def aggregate(chunks, expected_chunks, threshold=0.5):
    """Require every chunk; a missing/failed chunk must never become a negative."""
    if expected_chunks < 1 or not 0 <= threshold <= 1:
        raise ValueError('Invalid chunk count or threshold')
    if len(chunks) != expected_chunks or {r['index'] for r in chunks} != set(range(expected_chunks)):
        raise ValueError('Missing or duplicate chunks')
    if any(r['status'] != 'complete' for r in chunks):
        return {rule: {'status': 'failed', 'score_a': None, 'detected': None}
                for rule in ['max', 'mean']}
    values = [validate_probabilities(r['probabilities'])['A'] for r in chunks]
    scores = {'max': max(values), 'mean': sum(values) / len(values)}
    return {rule: {'status': 'complete', 'score_a': score, 'detected': score >= threshold,
                   'threshold': threshold, 'chunks': expected_chunks}
            for rule, score in scores.items()}
