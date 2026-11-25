# GLiDE-9B experiments

Each folder contains the question, method, evaluated inputs, results and provenance.

- [GLiDE-9B — full context, highest answer](full_context_highest/README.md): Measure detection when GLiDE sees the full rendered transcript and chooses its most likely answer.
- [GLiDE-9B — full context, sampled answers](full_context_sampled/README.md): Explore how sampling labels changes the same full-input classifier, alongside the sampled Qwen baseline.
- [GLiDE-9B — full context, P(A) ≥ 0.5](full_context_threshold/README.md): Compare full-input detection with chunk aggregation using the same binary probability threshold.
- [GLiDE-9B — chunks, maximum P(A)](chunks_max/README.md): Test whether judging smaller pieces helps detection, using the strongest local signal.
- [GLiDE-9B — chunks, average P(A)](chunks_mean/README.md): Test whether judging smaller pieces helps detection, using the average signal across pieces.
- [Qwen3-32B summaries → GLiDE-9B](qwen_summaries/README.md): Test whether a decision model benefits from reading compact evidence summaries instead of the raw transcript.
- [GLiDE-9B — installation and basic demo](smoke_and_demo/README.md): Check installation and learn how yes/no probabilities and multiple-choice decisions work.
- [GLiDE-9B — length, memory and runtime pilot](context_length_pilot/README.md): Check whether full-length reasoning fits in memory and whether simple evidence remains detectable as input length grows.

[All-model comparison](../../README.md)
