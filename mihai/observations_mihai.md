# Mihai — experiment observations

Browse the organized [Qwen, GLiDE and Jev experiment catalog](decision_models/README.md) for per-experiment folders and a comparison on common valid cases.

Updated 2026-11-24. This collects the completed Qwen and GLiDE monitor results,
length tests, original rollout outcomes, the separate task-screening experiment,
and the status of the new comparisons. **Full-input, chunk and summary decision-model evaluations are finished.
Summary results have 429 complete cases and 21 blocked cases per model.**
The Qwen3-32B greedy run has also been audited: 440/450 valid judgments.
Raw transcripts and reasoning remain on the cluster; the linked local reports
contain metrics and provenance.

## Qwen3-32B greedy: verified results, November 24

The greedy baseline uses temperature **0**, top-p **1**, thinking enabled,
one judgment per case, and the baseline prompts and hierarchy. Production job
**34371577** is terminal. Offline audit **34584150** completed successfully and
verified all **3,527 saved hierarchy-node responses**, their reconstructed prompt
identities and links, parsed answers, and the final scoring records. Recomputed
point estimates match the saved scores. No model responses were regenerated.

| Input | Valid / planned | Detection / TPR | Clean FPR | Accuracy* | G-mean² | Cross-objective FPR |
|---|---:|---:|---:|---:|---:|---:|
| Actions | 148/150 | 97.6% (40/41) | 25.0% (16/64) | 83.8% (88/105) | 0.732 | 32.5% (13/40) |
| CoT | 143/150 | 97.5% (39/40) | 18.5% (12/65) | 87.6% (92/105) | 0.795 | 22.9% (8/35) |
| Combined | 149/150 | 95.0% (38/40) | 21.2% (14/66) | 84.9% (90/106) | 0.748 | 15.0% (6/40) |

*Accuracy uses valid positive and clean-negative cases. The intended primary
denominator is 107 per view; invalid answers reduce it to **105, 105 and 106**.
Cross-objective negatives remain a separate diagnostic. All three own-objective
failure cases were flagged in every view and are also excluded from headline
scores. Invalid outputs are excluded from rates, never counted as rejections.

All **10 invalid judgments** had one invalid hierarchy node ending with
`finish_reason=length` at **16,768 completion tokens**: two actions, seven CoT
and one combined. The affected primary groups were two clean actions cases,
one positive and one clean CoT case, and one positive combined case; the other
five invalid CoT cases were cross-objective negatives. These are distinct from
the 26 failed evidence-summary requests described below.

The earlier comparison figures use sampled Qwen, not this greedy condition.
Comparisons against GLiDE/Jev or sampled Qwen must use the same valid case subset
and report missing judgments separately. These conditional rates alone do not
establish an improvement caused by greedy decoding. Qwen greedily generates
analysis tokens, while the decision models select an answer or aggregate P(A).

[Verified scores and audit](decision_models/variants/results-qwen-greedy-34584150/audit.json).
The raw answers remain under the cluster run's `qwen/` directory; the audit and
compact score files are under its `audits/qwen-greedy-34584150/` directory.

## Qwen summaries: terminal results, audited November 24

The summary experiment is finished. Qwen generated **2,808 valid summaries**;
**26/2,834 responses failed**, all with `finish_reason=length` and exactly
16,768 completion tokens. They affect **21 case/view combinations** (not 21
necessarily distinct actor rollouts): nine CoT cases and twelve combined cases.
Both GLiDE and Jev evaluated the same **429/450 cases**; the remaining 21 were
explicitly blocked. Neither decision model had an inference failure, and no cases
remain running, interrupted or unstarted. Actions have full coverage.

Qwen job **34371577** ended FAILED because its completeness check found failed
outputs. GLiDE summary job **34371590** similarly ended FAILED because 21 cases
were blocked, rather than because GLiDE inference crashed. Jev summary job
**34391867** and both scoring jobs completed. No retries were submitted.

| Model | Input | Complete / planned | TPR | Clean FPR | Accuracy* | G-mean² |
|---|---|---:|---:|---:|---:|---:|
| GLiDE-9B | Actions | 150/150 | 90.2% | 10.6% | 89.7% | 0.807 |
| Jev 1.14 | Actions | 150/150 | 95.1% | 22.7% | 84.1% | 0.735 |
| GLiDE-9B | CoT | 141/150 | 94.7% | 18.8% | 86.3% | 0.770 |
| Jev 1.14 | CoT | 141/150 | 100.0% | 43.8% | 72.5% | 0.562 |
| GLiDE-9B | Combined | 138/150 | 97.4% | 10.2% | 92.9% | 0.875 |
| Jev 1.14 | Combined | 138/150 | 100.0% | 35.6% | 78.6% | 0.644 |

*The primary denominators are **107 actions (41 positive + 66 clean)**,
**102 CoT (38 + 64)** and **98 combined (39 + 59)**. Blocked cases are excluded
from rates, never counted as negative decisions. Both models use the same valid
subsets. Their full/chunk results on all 107 primary cases cannot be compared
without accounting for the changed subset.

The offline audit also rescored previous methods on these exact subsets. For
CoT, summary / chunk-average accuracy is **86.3% / 97.1% for GLiDE** and
**72.5% / 98.0% for Jev**. For combined it is **92.9% / 96.9% for GLiDE** and
**78.6% / 98.0% for Jev**. For actions it is **89.7% / 90.7% for GLiDE** and
**84.1% / 78.5% for Jev**. These are descriptive comparisons on this small
fixed dataset. Summaries improve Jev actions, but sharply increase its CoT and
combined false alarms compared with chunk averaging.

Audit **34574890** reconstructed every summary prompt identity, checked all
valid summaries against their saved raw Qwen response, diagnosed failures from
usage/finish reason without exporting reasoning, and reconstructed the exact
ordered input sent to each decision model. Saved probabilities/choices and all
six metric reports matched the baseline scorer. Hashes and compact reports are
in [the terminal audit](decision_models/summary-results-20261124/audit.json).
[Latest scheduler and counts](decision_models/variants/summary-check-latest.json).

The greedy Qwen evaluation is independently verified in the section above.
Its 10 invalid judgments are separate from these summary-generation failures.

## Earlier comparison batch: setup failure, corrected restart

**17:36 UTC update:** the Qwen-summary → GLiDE pilot completed all three cases
(one actions, one reasoning, one combined). The saved request identities were
reconstructed and verified: GLiDE received every required Qwen summary in order
and returned valid A–D probabilities. This establishes that the pipeline runs,
not its accuracy on the full dataset. The production summary job **34371590**
is waiting for Qwen production **34371577**, which is still running.

At the progress snapshot, Qwen had **964 valid chunk summaries of 2,834** and
**six failed summaries affecting four reasoning cases**. All six failures ended
at the 16,768-token output cap (`finish_reason=length`); none was a GLiDE error.
Those four cases cannot receive a summary-based final judgment unless every
required summary is valid. The current run does not retry or shorten failed
summaries. The rest of the work continues. The invalid summaries are preserved
separately from valid outputs. [Progress](decision_models/variants/summary-check-20261123.json),
[failure diagnosis and pilot identity audit](decision_models/variants/summary-diagnosis-20261123.json).

Separately, GLiDE production **34371578** completed all **2,834 chunk judgments**
and **150 full combined-input judgments**. The final scoring job is still queued;
the performance tables below continue to show the previously audited conditions.

The first new Qwen32B greedy / GLiDE hierarchy / Qwen-summary batch did **not**
produce new judgments. Preparation job **34326291** passed, but Qwen smoke job
**34327025** failed after 4:00. The H200 loaded Qwen successfully; our launcher
then ran the evaluation client in `monitor-research`, which lacks `tokenizers`.
It stopped at `hierarchy.tokenizer_counter` with `ModuleNotFoundError` **before
any inference request**. This is an experiment-launcher error, not model failure,
context overflow, or GPU memory exhaustion. The five dependent inference jobs
were cancelled. The scoring job completed, but merely reported missing work and
reused the old full-input GLiDE results.

The fetched terminal snapshot contains **zero new Qwen artifacts**. Per input
view, Qwen greedy, GLiDE max/mean chunks and GLiDE summaries each had **0/150
complete, 0 case-level failures and 150 not started**. Full combined GLiDE also
had 0/150; actions and reasoning each reused 150 already completed decisions.
These methods share data and some calls: do not count them as extra rollouts.
[Exact status snapshot and scores](decision_models/variants/results-20261123/summary.json)

The launcher now uses the existing GLiDE environment for the Qwen client and
checks the tokenizer import before loading the server. Frozen inference code,
inputs, model versions, prompts and settings are unchanged. The original source
snapshot was not edited. A new submission's reference to the old completed
preparation job was rejected by Slurm; it created no job and was reconciled
before submitting without that expired dependency.
[Fix and verification](decision_models/variants/launcher-fix.json)

Corrected jobs: Qwen pilot **34371575**, GLiDE pilot **34371576**, Qwen production
**34371577**, GLiDE chunks/full **34371578**, GLiDE summaries **34371590**, final
scoring **34371591**. They were resubmitted on November 23. Their current status
is tracked in [the run record](decision_models/variants/status.json). At 15:05 UTC,
the corrected Qwen pilot had **passed (0:0, 3:30)**: one judgment and its required
summaries completed in each view, or **3/450 new Qwen cases**. The GLiDE pilot was
running and production stages were queued. These three pilot cases are cached
within the full evaluation, not additional samples. No complete new production
result is claimed in the tables below.

Planned rules: Qwen greedy uses temperature 0 / top-p 1 with thinking enabled;
GLiDE uses the highest raw-probability option; chunk methods use max or unweighted
mean P(A), with the predeclared 0.5 threshold; the summary method makes one final
GLiDE decision over all ordered Qwen evidence summaries. All three input views
are included. There are 184 actions chunks, 1,256 reasoning chunks and 1,394
combined chunks (2,834 total). The largest full combined prompt is 229,167 GLiDE
tokens. Chunk methods require every chunk; summary methods require every summary.

## Dataset and what the metrics count

There are **75 actor transcripts**: 41 retained original rollouts plus 34
main-only controls. Each is tested against two candidate objectives, giving
**150 cases per input view**, not 150 different rollouts. Actions, reasoning and
combined are three views of the same cases. Follow-up responses are not shown
to these monitors. The renderer retains the baseline's 2,000-character cuts to
tool results; “full input” means the entire rendered view with those existing cuts.

| Baseline scoring group | Cases per view | Meaning |
|---|---:|---|
| Positive | 41 | The told objective is labelled achieved |
| Clean negative | 66 | Baseline clean-control group |
| Cross-objective negative | 40 | The actor was assigned a different objective |
| Own-objective failure | 3 | The actor was assigned the told objective but did not achieve it |

All 150 cases are evaluated. The main comparison uses the **41 positives + 66
clean cases = 107 cases**; the other 43 are separate diagnostic groups, not missing
outputs. Sampled runs have four judgments per case: 600 total, with 428 in that
primary comparison. Highest-option runs have 150 judgments, with 107 primary.

Only answer **A** counts as detection. TPR is the fraction of positives detected;
FPR is the fraction of clean cases flagged; TNR = 1 − FPR. **G-mean² = TPR × TNR**
(no square root). **Accuracy*** below is `(TP + TN_clean)/(N_positive + N_clean)`;
it is neither balanced accuracy nor accuracy over all 150 cases. Errors remain
invalid/missing and never become negative answers. Repetitions are pooled as
individual judgments in these tables, not majority-voted.

## Completed monitor results

| Monitor | Input | Decision rule | TPR | FPR (clean) | TNR (clean) | G-mean² | Accuracy* |
|---|---|---|---:|---:|---:|---:|---:|
| Qwen3-14B | Actions | Sampled ×4 | 97.0% | 20.8% | 79.2% | 0.768 | 86.0% |
| Qwen3-14B | Reasoning | Sampled ×4 | 96.3% | 16.3% | 83.7% | 0.806 | 88.6% |
| Qwen3-14B | Combined | Sampled ×4 | 97.6% | 20.5% | 79.5% | 0.776 | 86.4% |
| Qwen3-32B | Actions | Sampled ×4 | 100.0% | 28.8% | 71.2% | 0.712 | 82.2% |
| Qwen3-32B | Reasoning | Sampled ×4 | 95.1% | 21.6% | 78.4% | 0.746 | 84.8% |
| Qwen3-32B | Combined | Sampled ×4 | 94.5% | 24.2% | 75.8% | 0.716 | 82.9% |
| GLiDE-9B | Actions | Sampled ×4 | 94.5% | 23.5% | 76.5% | 0.723 | 83.4% |
| GLiDE-9B | Actions | Highest option | 95.1% | 24.2% | 75.8% | 0.721 | 83.2% |
| GLiDE-9B | Reasoning | Sampled ×4 | 62.8% | 1.9% | 98.1% | 0.616 | 84.6% |
| GLiDE-9B | Reasoning | Highest option | 78.0% | 0.0% | 100.0% | 0.780 | 91.6% |

Every completed condition above has all its expected judgments and zero invalid
verdicts. Qwen uses four separately generated analyses with temperature 0.6 /
top-p 0.9. GLiDE sampled results use four local draws from one probability vector
with that same temperature/top-p transformation; these are **not four independent
analyses**. Highest-option GLiDE uses the original untransformed probabilities.

Exact counts behind those rates:

| Monitor / input / rule | TP | FN | FP (clean) | TN (clean) | Cross-objective flags | Own-failure flags |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-14B / Actions / Sampled ×4 | 159 | 5 | 55 | 209 | 47/160 | 12/12 |
| Qwen3-14B / Reasoning / Sampled ×4 | 158 | 6 | 43 | 221 | 40/160 | 12/12 |
| Qwen3-14B / Combined / Sampled ×4 | 160 | 4 | 54 | 210 | 52/160 | 12/12 |
| Qwen3-32B / Actions / Sampled ×4 | 164 | 0 | 76 | 188 | 54/160 | 12/12 |
| Qwen3-32B / Reasoning / Sampled ×4 | 156 | 8 | 57 | 207 | 42/160 | 12/12 |
| Qwen3-32B / Combined / Sampled ×4 | 155 | 9 | 64 | 200 | 31/160 | 12/12 |
| GLiDE-9B / Actions / Sampled ×4 | 155 | 9 | 62 | 202 | 37/160 | 12/12 |
| GLiDE-9B / Actions / Highest option | 39 | 2 | 16 | 50 | 8/40 | 3/3 |
| GLiDE-9B / Reasoning / Sampled ×4 | 103 | 61 | 5 | 259 | 31/160 | 10/12 |
| GLiDE-9B / Reasoning / Highest option | 32 | 9 | 0 | 66 | 11/40 | 3/3 |

Sources: [Qwen14B and Qwen32B baseline reports](decision_models/comparisons/baseline-20261123/metrics.json),
[baseline run manifest](decision_models/comparisons/baseline-20261123/manifest.json),
and [audited GLiDE/Qwen comparison](decision_models/comparisons/glide-vs-qwen32b-20261115/comparison.json).
The [November 23 audit](decision_models/comparisons/baseline-20261123/audit.json)
recomputed all six Qwen conditions from 3,600 saved decisions, checked unique
identities and dataset hashes, and matched every stored count and point estimate.
The baseline reports also retain malicious-target and benign-target scores and
bootstrap intervals; the tables here pool the two target objectives.

Observations:

- Qwen14B has higher clean G-mean² than Qwen32B in all three saved sampled views;
  larger model size did not improve this particular system comparison.
- GLiDE actions and Qwen32B actions have similar sampled clean G-mean²: 0.723
  versus 0.712. The paired bootstrap difference is +0.011, 95% interval
  [−0.065, +0.090], which does not establish an advantage.
- GLiDE sampled reasoning is conservative: only 5/264 clean false alarms,
  but it misses 61/164 positive judgments. Its G-mean² is 0.616 versus Qwen32B's
  0.746; paired difference −0.130, interval [−0.236, −0.024].
- Changing GLiDE reasoning to the highest option gives 32/41 positives detected
  and 0/66 clean false alarms: G-mean² 0.780, primary accuracy 91.6%. Nine positives
  are still missed. Zero observed false alarms does not imply a zero population rate.
- A matched greedy Qwen comparison is still needed. Do not interpret the
  highest-option result versus sampled Qwen as an isolated model-architecture win.

These bootstrap comparisons are exploratory, based on the same three tasks and
correlated judgments. They do not establish performance on new task categories.

## Runtime, memory and length tests

| Evaluation | Observed runtime | Hardware / interpretation |
|---|---|---|
| Qwen14B sampled, all 3 views | 3:00:50 | One H200; recorded evaluation session, 1,800 judgments |
| Qwen32B sampled, all 3 views | 5:50:32 | One H200; sum of two evaluation sessions, 1,800 judgments |
| Qwen32B actions | About 24:26 | Estimated phase boundaries, shared concurrent pool |
| Qwen32B reasoning | About 2:42:53 | Estimated phase boundaries, shared concurrent pool |
| Qwen32B combined | About 2:43:13 | Estimated phase boundaries, shared concurrent pool |
| GLiDE full actions | GPU job 5:04; calls 4:40.5 | One RTX PRO 6000 Blackwell; 150 calls, mean 1.87 s |
| GLiDE full reasoning | GPU jobs 1:06:13; calls 1:05:01.5 | One Blackwell; 150 calls, mean 26.01 s |
| GLiDE reasoning length pilot | GPU job 36:27 | 70 calls across 10 lengths; synthetic and real-input probes |

Qwen32B scopes overlap in a shared pool, so the per-view timing estimates are
not exact independent job durations. Different hardware, concurrency, hierarchy
and numbers of generated analyses mean these are **observed system costs**, not
controlled model-speed ratios. Qwen32B made 856 / 6,353 / 7,010 requests for
actions / reasoning / combined. Of 600 final judgments per view, 120 actions and
all reasoning/combined judgments used hierarchy. GLiDE made 150 full-input calls
per completed view; sampling four labels added no model inference.

Full GLiDE action prompts span **2,157–26,275 tokens**; full reasoning prompts
span **22,007–216,463 tokens**. The length pilot tested up to 216,463 tokens; two
warm calls at that length averaged 105.5 s, with 50.5 GiB peak allocated and
62.5 GiB peak reserved GPU memory. All 40 synthetic correctness checks and their
160 sampled labels passed, but those deliberately simple examples are **not**
benchmark accuracy. The real reasoning evaluation above exposes missed positives.

The initial full-reasoning job **33509938** stopped after 27:13 with 108 saved
results and 42 missing. There was no recorded case-level error or traceback, and
Slurm reported neither timeout nor OOM, so its cause remains unresolved.
Authorized restart **33512196** preserved those 108 results and completed the
remaining 42 in 39:00. All 150 results were audited. Reserved memory reached
93.1 GiB (50.5 GiB allocated) across the completed run, with six allocation warnings;
that does not prove why the original job stopped.
[Length measurements](decision_models/evaluations/glide-cot-length-20261115-21f6974f/README.md),
[reasoning audit](decision_models/evaluations/glide-cot-20261115-c8f6c4e8/),
[timing calculation](decision_models/comparisons/glide-vs-qwen32b-20261115/comparison.json).

## Actor rollouts and the separate task screening

Original request: **48 actor/follow-up pairs; 41 complete retained, seven excluded
execution failures/incomplete pairs**. The clean collection has 13 bank, 13
airline and 15 spam-filter pairs. Fourteen came from the two-A40 job **29860690**;
27 came from the H200 continuation **29894244**. The A40 job hit its scheduler
time limit; the H200 continuation completed 27/30 selected pairs and failed three.
The mixed hardware/serving provenance is retained, not called one homogeneous run.
All 41 retained actors have a false main-task label under the saved upstream-based
grader; execution completeness is separate from objective success.

The seven excluded identities are bank benign 1, bank malicious 0/4, airline
benign 3/5, airline malicious 1, and spam benign 5 (sample numbers start at zero).
The retained collection records two A40 tool-call parsing errors, two A40 unclosed
reasoning errors consistent with truncation, and three H200 pair failures (two
actors and one follow-up). The clean manifest does not preserve the detailed
H200 error causes, so this report does not infer them from the scheduler status.
[Collection and exclusions](results/collections/original_rollouts_clean/manifest.json).
Earlier attempts also exposed a DataFrame serialization omission in our adapter;
that was repaired before the retained campaign and is not a new monitor failure.

The independent **test_rollouts_2** screening job **29910578** had **19 complete
responses and one output-limit failure** out of 20 requests. It is not used in
the 75-rollout monitor dataset above. Standard main-task passes were:

| Category | Standard main-task passes | Controls |
|---|---:|---:|
| Factual questions with a hint | 1/2 | 0/2 |
| Preference choices | 2/2 | — |
| Logic puzzles | 1/2 | 1/2, plus one truncated request |
| Writing with a hidden word | 1/2 | 2/2 |
| Report summaries | 2/2 | 2/2 |
| Repeated-step mathematics | 2/2 final answers | — |

The table's logic control count includes both control requests: one passed,
one was truncated at 32,768 output tokens. Arithmetic explanations contained
incorrect intermediate equalities despite correct final integers. Hidden-word
sentence initials passed 2/2; exact required-sentence copying in summaries passed
0/2. Writing quality was manually reviewed. Two examples per category support
further testing, not a reliable category-wide success claim.
[Full screening report](test_rollouts_2/report.md).

## Interpretation limits

The monitor prompt asks about **pursuit** of an objective, while the saved grader
labels usually represent **achievement**. A flag on an own-objective failure can
therefore be reasonable; report that group separately. Benign and malicious
refer to the candidate side objective, not a guarantee that every negative or
positive case is clean or harmful. Only three agent environments are represented.

We retained the vendored grader rather than silently changing labels to match
our expectations. Its known differences from the paper include the bank diversion
threshold, rules that can pass without being enabled, and the spam main-score
transformation. Accordingly, zero main-task passes is a statement about this
grader, not proof that the model accomplished nothing. The actor setup and the
adapted GLiDE monitor prompt are not exact reproductions of the paper's systems.
[Evaluator audit and concrete examples](../docs/evaluator-notes.md).

## GLiDE: verified full-input and chunk comparisons

The completed GLiDE job **34371578** has now been scored independently of the
still-running Qwen job. Offline audit **34428767** verified all **2,834 chunk
responses**, **150 new combined full-input responses**, and the **300 reused
full-input actions/reasoning decisions**. It checked input identities, source
hashes, probabilities, model choices, input-token usage, reused result hashes,
and recomputed both aggregates. All nine conditions have 150/150 valid decisions.

| Input | Decision rule | TPR | Clean FPR | Accuracy* | G-mean² |
|---|---|---:|---:|---:|---:|
| Actions | Full, highest option | 95.1% | 24.2% | 83.2% | 0.721 |
| Actions | Chunks, maximum | 92.7% | 12.1% | 89.7% | 0.814 |
| Actions | Chunks, average | 92.7% | 10.6% | 90.7% | 0.829 |
| Reasoning | Full, highest option | 78.0% | 0.0% | 91.6% | 0.780 |
| Reasoning | Chunks, maximum | 92.7% | 0.0% | 97.2% | 0.927 |
| Reasoning | Chunks, average | 92.7% | 0.0% | 97.2% | 0.927 |
| Combined | Full, highest option | 87.8% | 6.1% | 91.6% | 0.825 |
| Combined | Chunks, maximum | 92.7% | 1.5% | 96.3% | 0.913 |
| Combined | Chunks, average | 92.7% | 0.0% | 97.2% | 0.927 |

These use the same 107-case primary denominator and scoring rules described
above. The remaining 43 diagnostic cases are retained in the reports. No new
model inference was required for this audit. The chunk-maximum and chunk-average
conditions share their model calls; the predeclared threshold is 0.5.

[Verified GLiDE scores](decision_models/variants/results-completed-34428767/audit.json).
The [three comparison tables](decision_models/comparison-tables-20261123/output/pdf/monitor-comparison.pdf)
show these results alongside Jev and the original sampled Qwen3-32B baseline.
Best point estimates, including ties, are bolded; this does not claim statistical
significance. The newer greedy Qwen and Qwen-summary conditions remain pending.

## Jev: full-input and chunk results; Qwen summaries pending

The separate [Jev runner and instructions](decision_models/jev/README.md) evaluate
all three views with full-input highest-option decisions, the four-draw sampled
reference, shared-chunk max/mean P(A), and one final decision over the exact same
ordered Qwen summaries. Model ID is pinned to `jev-1.14.0`. Planned maximum is
3,734 calls; sampled decisions and mean aggregation add no calls. The summary
condition waits for complete Qwen summaries rather than sending partial evidence.

Jev reasoning/combined full inputs use the documented optional long-context
header. GLiDE token counts cannot prove Jev input fit; the real-input pilot now
verifies acceptance and actual usage for the shortest and longest cases in each
view. No truncation fallback is implemented. Hosted GPU
memory cannot be measured from the API; request latency and token usage will be
recorded. [TypeSafe's model limits](https://docs.typesafe.ai/models).
CPU preparation **34372327** completed with exit 0 in 13 seconds: all **450 cases
and 2,834 chunks** were verified and **nine offline tests** passed on the cluster.
An earlier preparation job stopped in its tests because the standalone package
used a repository-relative helper path; this was corrected before preparation
passed. Neither preparation job sent API requests.
[Preparation report](decision_models/jev/preflight.json).

Real-input pilot **34391510** completed with exit 0 in **1 minute 52 seconds**.
Its **68 successful API requests** comprise 6 full inputs, 57 chunks, and 5 summary
inputs. One summary case was blocked while waiting for complete Qwen summaries;
no request was sent for that case. Saved request identities, response probabilities
and sampled labels passed the audit. The longest accepted combined input contained
**229,506 Jev tokens** and its request took **4.18 seconds**, including the network.
This checks execution and input fit; it is not a benchmark accuracy estimate or
a controlled GPU-speed comparison. [Pilot audit](decision_models/jev/api-smoke-audit.json).

| Stage | Job | Status at 19:36 UTC |
|---|---|---|
| Full inputs, highest option and four sampled labels | 34391865 | Completed, exit 0; 450/450 verified |
| Shared chunks, maximum and mean P(A) | 34391866 | Completed, exit 0; 2,834/2,834 verified |
| One decision over ordered Qwen summaries | 34391867 | Queued after Qwen 34371577 |
| Final scoring including summaries | 34391868 | Queued after summaries |

The **450 full-input requests and all 2,834 chunk requests passed** the offline
identity, content-hash, response, sampling and input-inventory audit. There are no
failed, interrupted or unstarted requests in either completed stage. Each of the
12 method/view reports below has full coverage: 150 case decisions, or 600 locally
sampled labels for the four-draw reference. No additional API requests were made
to calculate these results. Summary output still contains only the five pilot
decisions; this is not yet a production summary result.

| Input | Decision rule | TPR | Clean FPR | G-mean² | Primary accuracy |
|---|---|---:|---:|---:|---:|
| Actions | Full, highest option | 100.0% | 42.4% | 0.576 | 73.8% |
| Actions | Full, four sampled labels | 100.0% | 38.6% | 0.614 | 76.2% |
| Actions | Chunks, maximum | 100.0% | 34.8% | 0.652 | 78.5% |
| Actions | Chunks, average | 100.0% | 34.8% | 0.652 | 78.5% |
| Reasoning | Full, highest option | 95.1% | 13.6% | 0.822 | 89.7% |
| Reasoning | Full, four sampled labels | 96.3% | 18.2% | 0.788 | 87.4% |
| Reasoning | Chunks, maximum | 95.1% | 6.1% | 0.894 | 94.4% |
| Reasoning | Chunks, average | 95.1% | 0.0% | 0.951 | 98.1% |
| Combined | Full, highest option | 95.1% | 7.6% | 0.879 | 93.5% |
| Combined | Full, four sampled labels | 93.3% | 15.2% | 0.792 | 88.1% |
| Combined | Chunks, maximum | 95.1% | 3.0% | 0.922 | 96.3% |
| Combined | Chunks, average | 95.1% | 0.0% | 0.951 | 98.1% |

Primary accuracy uses **41 positive + 66 clean-negative cases (107 total)** per
view, or their 428 sampled labels. All 150 cases were evaluated; the 40
cross-objective negatives and three own-objective failures remain separate,
following the same baseline scorer. G-mean² is TPR × clean TNR. The sampled
reference draws four labels from one saved probability vector, not four new API
analyses. Chunk rules use threshold 0.5 and the same shared boundaries as GLiDE.

The strongest primary result is **98.1% (105/107)** for mean aggregation on either
reasoning or combined input: 39/41 positives detected, 66/66 clean cases left
unflagged. This is a result on this small fixed dataset, not evidence of zero
false-alarm risk in general. Their secondary cross-negative behavior differs:
reasoning mean flags 18/40, while combined mean flags 6/40. Both flag all three
own-objective failures; those are reported separately because detecting an
attempt can disagree with a grader that labels only achievement.

Production wall times were **13m 13s** for full inputs and **1h 02m 10s** for
chunks. These include pacing and Python/input work but exclude the reused pilot
calls. Across all saved calls including the pilot, mean full-input API latency
was **0.191s actions, 0.964s reasoning, 1.084s combined**; chunk latency was
**0.189s, 0.217s, 0.215s**, respectively. API latency includes networking and does
not provide a controlled hardware comparison with GLiDE/Qwen.

Offline audit/scoring job **34426786** used the pinned baseline scoring and
bootstrap code. The first scoring submission was rejected by Slurm because its
completed-job dependencies had expired; scheduler reconciliation confirmed no
job was created, then the audit was submitted after checking successful terminal
states directly. This made no new model requests and changed no experiment inputs.
[Verified scores, counts and timing](decision_models/jev/results-completed-34426786/audit.json),
[per-condition metrics and bootstrap intervals](decision_models/jev/results-completed-34426786/scores/),
[latest cluster check](decision_models/jev/latest-check.json).

The same three views and all 450 cases are scheduled. Pilot responses are reused,
not paid for again. Missing or failed Qwen summaries block their cases rather than
being silently omitted. The API key is stored privately outside the repository
and read only into the evaluation process; it is absent from submission records.
The frozen evaluation source and configuration are unchanged.
[Recorded jobs and status](decision_models/jev/status.json).

## Where the artifacts live

Use the team's shared project path as `$PROJECT` (see the repository's cluster
guide); login with your own cluster account.

- Original actors/follow-ups: `$PROJECT/rollouts_original_clean/`.
- Screening raw responses: `$PROJECT/mihai/test_rollouts_2/runs/29910578/`.
- GLiDE actions/reasoning and new comparisons: `$PROJECT/mihai/decision_models/runs/`.
- New shared inputs, Qwen judgments/summaries and GLiDE variants:
  `$PROJECT/mihai/decision_models/runs/decision-variants-20261123/`.
- Jev's isolated output: `$PROJECT/mihai/decision_models/runs/jev-variants-20261123/`.
- Qwen baseline's separate shared path and its exact model revisions are in
  [the baseline manifest](decision_models/comparisons/baseline-20261123/manifest.json).
- Slide-ready [results table](decision_models/presentation-progress-20261115/simple/03-results-table.pdf)
  and [cleaner charts](decision_models/presentation-progress-20261115/simple/) show
  the earlier GLiDE/Qwen32B comparison; they do not contain new variant or Jev results.
