# Experiment validity review

Reviewed against cluster commit `476f186` on 2026-11-24. The raw run artifacts
are only on the cluster. The [compiled results](results.md) therefore preserve
reported numbers; they are not an independent verification of those numbers.

No currently available evidence establishes that a monitor experiment must be
rerun. Two silent correctness risks need cluster provenance checks before the
results can be considered audited. Neither has been fixed in this branch, in
accordance with the requested review scope. Crash-only robustness problems are
outside this review.

## Findings that could require rerunning monitor inference

| Finding | Why a completed run could be wrong | Evidence of occurrence | Rerun decision |
| --- | --- | --- | --- |
| Requested and served models need not match | `scripts/run_experiment.py:make` warns on a name mismatch but proceeds. The comparison is a substring check. Verdicts are saved under the requested registry identity even if another model answered. | No evidence of a mismatch in the available tables. Managed jobs verify pinned downloads and use an explicit served-model name, reducing this risk. Raw manifests are needed. | Compare `manifest.served`, the contributing jobs' `serving-*.json`, model revisions and launcher arguments. If the wrong model answered, rerun the affected cells with the intended model. |
| Verdict reuse is not bound to rollout content | `spec._make_cell` hashes prompts/model/settings but not collection contents. `runner.unit_id` uses cell/item/objective/sample IDs. Resuming or `seed_monitor_run.seed` can reuse verdicts after transcripts or labels change under the same IDs. `score_run` loads current labels without checking the recorded collection hash. Manifest merging can overwrite earlier collection provenance. | No evidence that the frozen collections changed during this batch. Imports and retries make the path relevant, but do not establish a problem themselves. | Compare collection manifest hashes in runs, imports and metrics with verified current collections. A difference needs investigation: a path/metadata-only change is not proof that model input changed. Changed transcripts require rerunning affected units; labels alone may permit rescoring stored verdicts without inference. Identical hashes need no rerun. Missing historical provenance leaves uncertainty. |

The endpoint check only checks that a server advertises one model. A matching
name alone cannot prove which weights were loaded. Model revision and launch
provenance are needed too. The exporter includes these records when available,
but cannot recover overwritten session-specific identities.

Duplicate unit keys or an incomplete sample/objective grid can also give
misleading aggregate results: `score_run` considers a cell complete based on
record count, without checking grid uniqueness. The experiment launcher uses
exclusive locks and the importer rejects duplicates, so there is no current
evidence of this happening. The exporter checks actual key sets, not just counts.
Duplicated records can be deduplicated and rescored after review; missing
intended units require inference only for those units.

## Interpretation issues already applicable to the reported tables

**Invalid answers are excluded from rates.** This is the established scoring
policy, not a change introduced in this batch. Gemma E2B has reported coverage
0.602/0.127/0.147 for action/CoT/all; Qwen1.7B has 0.730/0.723/0.530. A high
conditional TPR or score does not establish strong performance over all intended
judgments. The report includes coverage alongside scores. No rerun is required
solely because an answer is invalid; changing the scoring policy is deferred.

**The scopes are not pure CoT versus Actions as defined in Monitoring
Monitorability.** `hierarchy.render_turn` includes visible assistant content in
`cot`, and excludes it from `action`. This follows the repository's existing
MonitorBench-style convention. It is suitable for comparing models under those
same scopes, but a claim specifically about reasoning alone would be unsupported
if visible assistant text contributed evidence. Quantifying that contribution
requires the raw actor transcripts. A pure-CoT experiment would require rerunning
the affected scopes after agreeing on the intended definition.
[Paper, Section 2.2](https://arxiv.org/html/2512.18311v1#S2.SS2).

**Inherited evaluator labels have known semantic limitations.** The bank
malicious check can pass below the paper's $5,000 target; bank benign counts
non-bank payment channels and does not require positive amounts. Spam side
checks can pass without the stated global/enabled behavior. These properties
are detailed in [evaluator notes](../docs/evaluator-notes.md). They are retained
upstream behavior and can affect ground-truth labels even when inference is
healthy. The paper describes stricter goals but does not resolve which code
paths generated its published results. This experiment measures detection of
the implemented labels; exact compliance with every task instruction is not
established. No relabeling or inference rerun has been made.
[MonitorBench, Appendix A.1.2](https://arxiv.org/html/2603.28590v1#A1.SS1.SSS2).

**Reported GPU-hours do not cover the full job.** The runner starts its wall
timer immediately before the monitoring thread pool, after server startup and
initial preparation. `costs.compute_by_monitor` calls that job time including
startup, which is inaccurate. This affects the interpretation of cost, not
detection scores. Use Slurm allocation times to recompute total GPU-hours;
no model rerun is needed. The consolidated report omits unsupported total-cost
and eager-speedup claims.

**Backend equivalence has not been established.** The cluster's CUDA fallback
sets `VLLM_USE_FLASHINFER_SAMPLER=0`; that setting disables the FlashInfer sampler,
not every possible FlashInfer/JIT path. Its log phrase “FlashInfer JIT disabled”
is broader than the setting guarantees. Serving manifests record toolkit paths
and vLLM versions, but not the complete environment. Neither matching nominal
sampling settings nor eager execution proves identical generated verdicts
across software versions. Preserve these differences as provenance. There is
no evidence here requiring discarding otherwise valid completed judgments.

The hierarchy follows recursive chunk-summary aggregation in MonitorBench,
Appendix A.2.1, Algorithm 1. Chunk limits, bin size, truncation, reference
tokenizer and aggregation wording are this repository's operational choices;
they must not be described as the official published aggregation prompt.
[MonitorBench implementation details](https://arxiv.org/html/2603.28590v1#A2.SS1).

## Collecting the missing evidence

From the updated checkout on the cluster:

```bash
bash junlin/export_results.sh
```

This reads `.env.cluster` and uses the saved analysis Python. It writes
`junlin/results/cluster-audit.json` without modifying source runs or making model
calls. The bundle contains metrics, manifests, serving provenance, artifact
hashes, grid/duplicate checks and recomputed point-estimate comparisons. It
retains the existing scoring rules. Intervals are copied, not recomputed.
Exit code 1 means there are findings to review, including missing evidence;
it is not a request to rerun inference. No traces, model weights or credentials
are included.

The source mapping matches the compiled cluster report: all Qwens from
`$ME/runs/baseline`, each Gemma from its own parallel run. A later Qwen1.7B
parallel run is not automatically substituted. Raw source selection must be
reviewed if those paths are no longer authoritative. Keep source files stable
while exporting. Existing launcher locks are respected; the source files are
hashed again to detect changes during export.

## Merge scope

The local pre-sync branch is preserved as
`backup/qwen-gemma-before-sync-20261124`. The experimental branch was reset to
`origin/qwen-gemma-experiments` at `476f186` before cleanup. The merge target is
`main`, the repository's default branch (there is no `master`).

Experiment-specific jobs, CUDA setup and cache-import helpers live in `junlin/`.
The existing `mihai/` files and shared baseline report match `main`. Shared code
changes are limited to optional pinned-registry support and serving options
needed by these experiments; defaults for existing Qwen jobs are retained.
Prompts, rollout datasets, vendored evaluators and scoring are unchanged.
This cleanup does not claim that scientific provenance has been fully verified.

Local validation: 334 CPU tests run, all successful with 10 skips for unavailable saved
rollout collections. The pinned reference tokenizer matched the frozen SHA-256.
All 288 copied metric estimates/intervals were checked against the source report
at `476f186`. Synthetic artifact tests exercise unchanged-source export,
recomputed point estimates, invalid-answer handling, wrong served-model names,
changed collection hashes, stale metrics and duplicate unit keys. GPU execution
and the actual cluster artifacts were not tested locally.
