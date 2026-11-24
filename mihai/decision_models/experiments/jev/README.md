# Jev 1.14 experiments

Each folder contains the question, method, evaluated inputs, results and provenance.

- [Jev 1.14 — full context, highest answer](full_context_highest/README.md): Measure whether Jev can detect the objective from the entire rendered transcript in one request.
- [Jev 1.14 — full context, sampled answers](full_context_sampled/README.md): Compare four sampled labels with the highest answer from the same Jev inference.
- [Jev 1.14 — chunks, maximum P(A)](chunks_max/README.md): Test whether judging smaller pieces helps detection, using the strongest local signal.
- [Jev 1.14 — chunks, average P(A)](chunks_mean/README.md): Test whether judging smaller pieces helps detection, using the average signal across pieces.
- [Qwen3-32B summaries → Jev 1.14](qwen_summaries/README.md): Test whether a decision model benefits from reading compact evidence summaries instead of the raw transcript.
- [Jev 1.14 — API and long-input pilot](api_and_length_pilot/README.md): Check the hosted interface, request identity and acceptance of short and long real inputs before production.

[All-model comparison](../../README.md)
