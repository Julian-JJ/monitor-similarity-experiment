"""Sample final A-D decisions; this does not generate or resample reasoning."""
import hashlib
import math
import random

LETTERS = "ABCD"


def sampling_distribution(probabilities, temperature=0.6, top_p=0.9):
    if set(probabilities) != set(LETTERS):
        raise ValueError("Expected probabilities for exactly A, B, C, D")
    p = [probabilities[letter] for letter in LETTERS]
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in p):
        raise ValueError("Invalid probabilities")
    if not math.isclose(sum(p), 1, abs_tol=1e-5):
        raise ValueError("Probabilities do not sum to one")
    if temperature <= 0 or not 0 < top_p <= 1:
        raise ValueError("Invalid sampling settings")
    # softmax(log(p) / T) is equivalent to raising probabilities to 1/T.
    weights = [x ** (1 / temperature) for x in p]
    total = sum(weights)
    ranked = sorted(range(4), key=lambda i: -weights[i])
    kept, cumulative = [], 0.0
    for i in ranked:
        kept.append(i)
        cumulative += weights[i] / total
        if cumulative >= top_p:
            break
    mass = sum(weights[i] for i in kept)
    return {letter: weights[i] / mass if i in kept else 0.0
            for i, letter in enumerate(LETTERS)}


def draw_answers(distribution, case_id, base_seed=0, samples=4):
    draws = []
    for sample in range(samples):
        # A stable per-case seed makes results independent of execution order.
        key = f"{base_seed}:{case_id}:{sample}".encode()
        seed = int.from_bytes(hashlib.sha256(key).digest()[:6], "big")
        letter = random.Random(seed).choices(list(LETTERS),
                    weights=[distribution[k] for k in LETTERS], k=1)[0]
        draws.append({"sample": sample, "seed": seed, "letter": letter})
    return draws
