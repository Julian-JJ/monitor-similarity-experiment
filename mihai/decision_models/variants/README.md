> For all completed experiments and the common-case comparison, see [the experiment index](../README.md). This page retains the runner and historical deployment notes.

# Greedy and hierarchical decision-model experiments

**November 24 update:** Qwen summaries are finished: 2,808 valid and 26 truncated. GLiDE and Jev each completed 429/450 cases; 21 were blocked. See [the audited results](../summary-results-20261124/audit.json).

The dated progress notes below retain earlier snapshots.

Status (2026-11-23, 17:36 UTC): corrected Qwen and GLiDE pilots passed. The summary pipeline was verified on all three input views. Qwen production is running; its summary output has six truncation failures across four cases so far. Full GLiDE chunks and combined-input production completed; summary production and final scoring are waiting for Qwen. See `status.json` and `summary-diagnosis-20261123.json`.

The confirmed scope is actions, CoT and combined, on the same 75 rollouts, with both told objectives: 150 cases per input type. The user confirmed all three scopes and one final decision over all ordered summaries.

| Condition | Procedure |
|---|---|
| Qwen32B greedy | Original MonitorBench prompts and baseline hierarchy; temperature 0, top-p 1, thinking on, one judgment per case. |
| GLiDE full, highest option | Reuse verified actions/CoT results after matching input hashes; evaluate full combined inputs once if they pass preflight. |
| GLiDE chunk maximum | Classify each shared chunk, take maximum raw P(A), flag at ≥ 0.5. |
| GLiDE chunk mean | Reuse those same chunk calls, take the unweighted mean of raw P(A), flag at ≥ 0.5. |
| Qwen summaries → GLiDE | Qwen greedily writes an evidence summary of every chunk without an A–D verdict. Concatenate all summaries in order; GLiDE picks its highest-probability A–D answer once. |

Max/mean P(A) are **binary scoring rules**, not four-way argmax. For example, A=0.4, B=0.3, C=0.2, D=0.1 selects A under argmax but is below the fixed 0.5 binary threshold. Save continuous scores so threshold curves can be reported later; do not tune the threshold on this test set. Missing or failed chunks invalidate the aggregate. Chunk means are not length-weighted.

## What stays fixed

- Framework commit `6043ff7a875bf6d2d792cec7df603c5cd019c647`, imported from the previously audited frozen CoT release. That release is never edited.
- Same two collection manifests and objective table; no labels, grading outcomes or actor system instructions enter inference requests.
- Same turn labels, 2,000-character tool-result cuts, reference tokenizer, 12,000-token chunk budget, 32,768-token Qwen context, 16,768 output reserve, 512-token input margin, bin size six, and single-pass-if-fits shortcut.
- Chunk text is identical across Qwen, GLiDE chunk rules and the summarizer. Prompts differ by model interface. Full-input GLiDE retains its existing adapter; a corresponding combined-input adapter is new.
- Qwen stays in thinking mode. Greedy decoding changes token selection, not whether it reasons. One request attempt per node; unlike the old baseline's allowance of two, invalid greedy replies are preserved without repeating them.
- GLiDE uses raw temperature-1 model probabilities, without temperature/top-p transformation or sampling. Its highest option counts as detection only if the winner is A.
- All 150 cases per scope remain represented, including cross-objective negatives and own-objective failures. Report all four scoring groups, coverage and failures. Label positive-plus-clean accuracy as a subset measure.

## Main code

- `run_variants.py`: prepare identical evidence chunks, run Qwen and GLiDE stages, cache requests, reuse earlier full-input results, and invoke the baseline scoring code.
- `aggregation.py`: the two short max/mean rules and probability validation.
- `prompts.py`: partial-transcript notice, evidence-only summary instructions, and GLiDE's final summary decision prompt.
- `combined-question.json`: the combined-input GLiDE adaptation with unchanged A–D choices.
- `run.sbatch`: CPU/GPU stage launcher with exit status and server cleanup.
- `freeze_package.py`: freeze a new deployment copy after finalizing configuration. Does not modify an existing release.

The summarizer targets at most 350 words per chunk, but actual output length is measured rather than assumed. Truncated/empty summaries or replies containing an explicit `<answer>A-D</answer>` are rejected. GLiDE receives Qwen's visible summary text, not Qwen's private reasoning output. All summaries must exist and fit the final prompt limit; never silently truncate or omit a summary. The summary condition is explicitly a **Qwen-assisted GLiDE system**, and its cost includes both models.

## Deployment sequence after access is restored

1. Reconcile existing jobs and receipts before any submission. Verify frozen framework inventory, models/revisions, reference tokenizer location/hash, baseline settings, collection hashes, and available environments/resources.
2. Copy this package to a new release directory outside the original frozen source. Finalize `config.json`, freeze inventory, and record its SHA256. Do not edit after submitting.
3. CPU `prepare` stage in the existing GLiDE environment: verify source, model files and data; render inputs; count prompts; save immutable `inputs.json` and `ready.json`. A length failure stops before GPU work.
4. Inspect preflight; smoke-test representative short and longest requests before committing to the full GPU workload. Use the existing H200 Qwen environment and existing Blackwell GLiDE environment.
5. Run `qwen` on one H200. It performs both the original greedy monitor and separate evidence summaries, caching every call. Run `glide-chunks` and the missing `glide-full` combined condition on Blackwell, sequentially within an allocation if practical.
6. Once Qwen summaries are available, run `glide-summaries` on Blackwell. A terminal partial Qwen job can still leave useful complete summary sets; incomplete sets remain blocked, never scored as negatives.
7. Run `score` on CPU, audit expected case identities, provenance and artifact completeness, and compare paired conditions. CPU score reports unfinished conditions explicitly rather than claiming overall completion.

Before each `sbatch`, use a submission lock, unique UUID/comment and durable intent/receipt. Reconcile any existing intent or uncertain response instead of blind resubmission. Submission receipts are saved under `receipts/` and on the cluster. The initial eight-CPU H200 request was definitively rejected by Slurm; corrected requests use six CPUs per H200, with a new UUID and name. Do not commit or push without a new request.

Raw inputs, summaries, reasoning and weights stay on the cluster. Only code, compact metrics, provenance and figures should be copied locally. The existing November 15 experiments remain separate.

## Validation

Run offline tests from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s mihai/decision_models/variants -v
bash -n mihai/decision_models/variants/run.sbatch
```

These validate the new logic, not model compatibility or cluster execution. GPU smoke tests and full-input preflight are still required. Final audit must verify each preserved/reused result against its expected request/configuration and report complete, failed, blocked and not-started counts for each condition.
## November 23 restart status

The initial Qwen smoke job 34327025 failed before inference because its client
environment lacked `tokenizers`. The corrected launcher uses the existing GLiDE
environment for that client. All submitted inference source/configuration files
remain unchanged; the separate launcher and its hash are in `launcher-fix.json`.
The corrected Qwen smoke job 34371575 passed all three views. See `status.json`
and `restart-observation.json` for the restarted jobs, exact times and progress.
The snapshot in `results-20261123/` describes the original failed launch, not the
later restart. Completed baseline results and limitations are consolidated in
[`observations_mihai.md`](../../observations_mihai.md).

