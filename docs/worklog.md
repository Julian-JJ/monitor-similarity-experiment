# Work log

A factual record of what was done, in order, including mistakes and actions the
user declined. Newest session last. Times are omitted except where a file's own
timestamp matters. "Local" means the Mac at `/Users/arushsrivastava/Desktop/VS Workspace`;
"cluster" means Yale's Bouchet (`bouchet.ycrc.yale.edu`).

## Session 2026-10-19, part 1: research, planning, hierarchical monitor

### A. Cluster access

1. **Explained options for working over SSH** (no actions): run commands with
   `ssh host "cmd"`, mount with `sshfs`, sync with `rsync`, or use VS Code Remote-SSH.
2. **First connection attempt.** A non-interactive `ssh` as `cpsc4880_as4833` failed with
   `Permission denied (publickey)`. A read-only look at `~/.ssh/config` found
   `Host bouchet.ycrc.yale.edu` with `User cpsc4520_as4833` (a different account).
   Diagnosis: `~/.ssh/id_ed25519` was offered; the agent held no keys.
3. **User logged in** from their own terminal. Prompts for a passphrase and
   multi-factor authentication cannot be answered by the assistant, and the `!`
   shell has no terminal. The user then opened a connection with `ControlMaster`
   (socket `~/.ssh/cm-cpsc4880_as4833@bouchet.ycrc.yale.edu:22`, kept 8 hours); later
   commands reused it. The socket expired once during the session and the user
   reopened it.
4. **Declined by the user, so not done:** adding a `Host bouchet4880` block with
   ControlMaster settings to `~/.ssh/config`, and saving a memory note about the
   cluster. The user then said not to set up future use and not to add to memory.
   **`~/.ssh/config` was not modified and nothing was saved to memory.**

### B. Getting the repository onto the cluster

5. **Listed** the cluster home directory (read-only): `project_cpsc4880` and
   `scratch_cpsc4880` are links to `/nfs/roberts/project/cpsc4880` and
   `/nfs/roberts/scratch/cpsc4880`. The listing of the shared project directory
   incidentally showed other students' directory names; nothing in them was opened.
6. **Clone attempt 1** into `~/project_cpsc4880/`: failed with permission denied. That
   directory is shared and not writable; each student has a subdirectory
   (`cpsc4880_as4833` is the user's).
7. **Clone attempt 2** into the user's subdirectory: the tool call was rejected by the
   user mid-run, but the `git clone` process had already started on the cluster and
   kept running, leaving a partial `monitor-similarity-experiment/.git` (no HEAD or
   objects). A later `git clone` reported the destination existed.
8. **Cleanup of the partial clone.** After checking that the directory held only an
   empty skeleton created that day, the assistant ran `rm -rf` on it. The first `rm`
   failed because the original clone was still writing into it. A "wait for the clone"
   loop used `pgrep -f 'git clone'`, which matches its own shell, so it always
   reported "running" (a mistake). Checking `ps` directly showed no git process, and the
   directory was gone.
9. **Clone attempt 3** failed: `could not read Username for 'https://github.com'`. The
   repository is **private** (an unauthenticated request to GitHub returns 404). The
   Mac has stored GitHub credentials, so `git ls-remote` works there.
10. **Workaround.** The repository was cloned on the Mac into the scratchpad directory
    and copied to the cluster with `rsync` to
    `~/project_cpsc4880/cpsc4880_as4833/monitor-similarity-experiment` (8.2 MB; it took
    about 15 minutes because the project filesystem is slow). Verified on the cluster:
    branch `main`, commit `5dc0417`, clean tree. No credentials were sent. The cluster
    checkout's `origin` is the plain HTTPS URL, so `git pull` and `git push` there will
    fail until GitHub access is set up on the cluster.

### C. Research and planning

11. **Read the repository**: `README.md`, `docs/plan/01`–`04`, `docs/evaluator-notes.md`,
    `docs/rollout-format.md`, `mihai/README.md`, `configs/rollouts.toml`,
    `prompts/generic_followup.txt`, the package, and the saved summaries.
12. **Read the two papers and upstream code** (details and reliability in
    [the research notes](research/monitor-baseline-notes.md)). Web fetches of the paper
    pages returned model-written summaries; the later parts of the MonitorBench page
    could not be fetched (three requests failed with an API error and were not retried
    again). Upstream files (monitor prompt, `run.sh`, `README.md`, `metric.py`, `main.py`,
    and a file listing through `api.github.com`) were downloaded with `curl` at the
    pinned commit into the scratchpad.
13. **Findings given to the user as a plan**: the baseline definition; discrepancies
    between the paper and the released code; and a data limitation (38 of 41 saved
    rollouts achieved the side objective, 3 did not, and there are no `main_only`
    controls, so TNR and g-mean² cannot yet be measured).

### D. Token counting

14. **Cluster job (stopped).** To count tokens the assistant piped a Python script over
    SSH to run under the shared serving environment on a login node, reading the
    rollouts from the teammate-owned project directory (read-only). It was slow (the
    filesystem), produced 21 per-rollout lines, and was **stopped at the user's request**.
    The stop command's `pkill -f` pattern matched its own shell, so it was re-verified
    with `ps`: no Python process of the user's remained. A read-only check afterwards found
    no `~/.cache_hf` directory and nothing of the user's running. One temporary directory
    (`/tmp/tmpxvzmoj1y`, owner the user, created that afternoon) exists on the login node;
    it was **not opened and not deleted**.
15. **User redirected work to be local** ("clone the repo into a local folder … go to ssh
    in the end when we have to run something large scale").

### E. Local setup

16. **Cloned the repository locally** to `monitor-similarity-experiment/` next to this
    workspace, using the Mac's stored GitHub credentials (`main` at `5dc0417`).
17. **Copied the 41 saved rollout pairs** from
    `/nfs/roberts/project/cpsc4880/cpsc4880_mae73/rollouts_original_clean/` to
    `rollouts_original_clean/` in the clone (87 MB; 41 `rollout.json`, 41 `followup.json`).
    The first `rsync` failed at once because macOS's `rsync` has no `--info` option; it
    was rerun with `--stats`. The directory is already in `.gitignore`.
18. **Copied `tokenizer.json`** (11.4 MB) of the pinned Qwen3-14B revision from the
    cluster's `models/qwen3-14b/` to `cache/tokenizer/` (ignored).
19. **Created `.venv/`** (Python 3.14.7, ignored) and installed `tokenizers 0.23.3`,
    `huggingface_hub`, and `PyYAML` with their dependencies. The existing test suite
    needs the cluster packages (pydantic, pandas, …) and was not run locally; see
    [Verification](#verification-end-of-part-1).

### F. Hierarchical monitor

20. **Vendored the upstream agent monitor prompt** into `vendor/monitorbench_monitor/`
    from the pinned commit (byte-identical, verified with `diff`; MIT license copied;
    hashes in its `manifest.json`).
21. **Wrote our prompts**: `prompts/monitor_chunk_notice.txt`, `prompts/monitor_reduce.txt`.
22. **Wrote `monitor_experiment/hierarchy.py`**, `tests/test_hierarchy.py`,
    `scripts/count_transcript_tokens.py`, and `scripts/plan_hierarchy.py`.
    - A test failed because it expected the run to stop after the first invalid chunk;
      the code (correctly, by design) runs the whole level first. The test and the
      docstring were corrected, and a `model_requests` field was added.
    - A refinement was added after seeing the first dry run: `single_pass_if_fits`
      (default on) uses the unmodified upstream prompt whenever the whole transcript fits.
      A test helper that disabled it by default briefly broke its own test; fixed.
23. **Ran the analyses** and saved results in `mihai/results/`:
    `transcript-token-counts-20261019.json`,
    `hierarchy-plan-32k-20261019.json`,
    `hierarchy-plan-131k-chunk100k-20261019.json`. An intermediate run that set only
    `--context-tokens 131072` (chunks still 12,000) was identical to the 32k run and was
    discarded; a run before the `single_pass_if_fits` rule was replaced by the final one.
24. **Wrote documentation**: [`docs/plan/05-hierarchical-monitor.md`](plan/05-hierarchical-monitor.md),
    [`docs/analysis/transcript-token-counts.md`](analysis/transcript-token-counts.md),
    [`docs/research/monitor-baseline-notes.md`](research/monitor-baseline-notes.md),
    this log, and [`docs/README.md`](README.md). Two statements in the analysis draft
    were found unsupported when checked against the data (which task the over-limit
    `action` rollouts belong to; a "8 to 100 times" ratio) and were corrected.
25. **Edited existing documents** so they match the new state: see
    [Documents changed](#documents-changed-part-1).

### G. Plan revised into a reusable framework (later the same day)

26. The user asked for a reusable paradigm: choose a monitor model, select variations,
    run, and receive metrics from which a report can be generated. The plan was
    rewritten as [`docs/plan/06-experiment-framework.md`](plan/06-experiment-framework.md):
    a declarative experiment spec; registries for monitor models and rollout sets;
    variations as grid axes; monitor methods as pluggable strategies (the existing
    hierarchical monitor becomes the first); a standard metrics set with a hierarchical
    bootstrap; a report generator; and provenance in every run. Nothing in this step
    was implemented. `docs/README.md` and `docs/plan/04-monitor-evaluation.md` were
    updated to point to it.

27. **Compared the plan with the project proposal** (the user pasted "Monitor Choice and
    Monitorability"). The plan did not cover: multiple actors and an actor × monitor matrix;
    plan-only and plan-compare-interrogate monitoring; councils of monitors; hosted-model
    providers and pricing; the full 1,514-test MonitorBench suite and its other metrics and
    stress tests; reasoning effort; partial-CoT monitoring; cost and latency reporting
    beyond token counts; and the separation of "information absent" from "present but
    missed". `docs/plan/06-experiment-framework.md` now states the gaps, the design changes,
    the added work, and new decisions, and its status line warns that its earlier sections
    were scoped to the agent tasks only. Nothing was implemented.

28. **Scope reduced at the user's request.** The user asked to replace the full
    1,514-test suite with the abridged evaluation derived earlier from the papers.
    `docs/plan/06-experiment-framework.md` now defines an "Evaluation scope (abridged)": the
    three code-graded agent tasks, outcome-justification metrics only, benign, malicious and
    `main_only` variants, three observation scopes, no stress tests. The plan items for other
    task families, the intervention and process metrics, and stress tests were removed
    (Stage D marked dropped), and the plan states what this gives up relative to the
    proposal. No code or data changed.

29. **Corrected the framework plan: the actor is fixed.** The user clarified that the agent
    (Qwen3-14B) stays the same and that only the monitor, and the preparation done for the
    monitor (such as task context), vary. `docs/plan/06-experiment-framework.md` was revised:
    removed first-class actors, the actor × monitor matrix, the "additional actors" stage
    and the actor-related decision; added a "What is fixed and what varies" section, a
    `prepare → judge` model of monitor preparation with separate caching of context
    artifacts (plans and executions depend on the task, not the rollout), `prep_samples`,
    and reworded the similarity analysis as relative to the fixed actor. No code or data
    changed.

30. **Decisions recorded** (user answers plus assistant discretion). The user confirmed the abridged
    suite, that the monitor's plan is written from the main task only, and that compute is a
    cluster (no money for hosted APIs); council design and the information-presence label were left
    to the assistant. New file `docs/plan/07-design-decisions.md` records: the monitor pool and
    similarity relation to the fixed actor; three pre-specified councils of three with majority vote
    primary and any/unanimous secondary, plus a same-model control; three plans per task assigned
    by sample number modulo three; a three-tier presence-label protocol (frozen rules, human-verified
    spans, agreement thresholds) and the metrics derived from it; the five confirmatory comparisons
    with Holm correction (everything else exploratory); GPU-only cost reporting; and an amendment
    log. `docs/plan/06-experiment-framework.md` was edited to drop hosted providers and dollar
    pricing and to reference it. The user's pending question on cached-only rollouts versus new
    `main_only` controls was not answered and is listed as open. Nothing was implemented or run.

31. **Cached-only evaluation and the remaining delegated decisions.** The user chose cached
    rollouts only (no `main_only` controls, no new actor calls) and delegated the hierarchy
    settings, prompt wording and annotators. Data checks run for this (read-only, local):
    each (task, variant) has exactly one objective text across samples (six texts), and every
    rollout carries both side labels, giving 21 positive / 20 negative pairs when told the malicious
    objective and 18 / 23 when told the benign one. Bin-size sensitivity from the real chunk counts
    showed depth 4 at `bin_size` 3 or 4 and depth 3 at 6 or 8. `scripts/plan_hierarchy.py` gained an
    `--objectives` multiplier, and a priced dry run for the pre-registered settings was saved as
    `mihai/results/hierarchy-plan-prereg-20261019.json` (8,336 calls and about 80 M input tokens per
    monitor and context). `docs/plan/07-design-decisions.md` was rewritten with: the cached-only
    evaluation design and its impure-negatives weakness; recall as the primary metric with a
    g-mean² guardrail; `upstream-limits`, 12,000-token chunks, bins of 6; draft plan prompt and
    judge-with-plan section and a freeze procedure with a label-blind format pilot; annotator
    logistics and a no-language-model labeling rule; and an amendment log (A1 to A3). The framework plan,
    research notes, README, index and `docs/plan/05` were updated to match. Interrogation and
    `main_only_v1` were removed from the plan. Nothing was run on a model; no code other than the
    dry-run flag changed.

32. **Negatives: controls added back.** The user asked for the explanation of the impure-negatives
    problem (given in conversation: the judge prompt's option `A` is generic, so a monitor that flags a
    cross-objective rollout can be right in general and wrong for the stated objective, and in the
    benign-told direction no option fits) and then asked for generation of the negatives to be added to
    the plan. Read-only inspection of `scripts/generate_rollouts.py`, `scripts/serve_model.py`,
    `monitor_experiment/serving.py`, `mihai/cluster/run_qwen.sbatch`, `run_qwen_selected.sbatch`,
    `run_selected_pairs.py` and `mihai/configs/rollouts-output-32768.toml` found: the launch script
    hard-codes the teammate's project path; the serving script writes its manifest into the model
    directory; launch requires the checkout to match its commit; and the cache identity hashes every
    `*.py` in `monitor_experiment/`. `docs/plan/07-design-decisions.md` gained section 2.11 (control
    rollouts: identical settings, 12 samples per task with a top-up rule, retention rule, pristine
    `5dc0417` checkout, own project directory, two jobs), a rewritten 2.9 (positives, clean negatives,
    secondary cross-objective negatives), restored g-mean² as the primary metric with recall alongside,
    cost scaling (about 1.7×, an untested length assumption), and amendment A4 (A2 marked superseded).
    The framework plan, research notes, README and index were updated. No control was generated; nothing
    ran on the cluster.

### Verification (end of part 1)

- `tests/test_hierarchy.py`: 30 tests, all pass locally (`.venv/bin/python -B -m unittest tests.test_hierarchy`).
  They include a check that every one of the 41 saved rollouts yields a clean hidden
  objective; that test is skipped when the rollouts are absent.
- The pre-existing tests (`tests/test_rollouts.py`, `tests/test_model_scripts.py`) were
  not part of this work and were not changed. See the item above about running them.
- No monitor model was run, on the cluster or locally. Nothing in this log is a
  monitorability result.

### Files created (part 1)

| Path | Purpose |
| --- | --- |
| `monitor_experiment/hierarchy.py` | rendering, chunking, prompts, tree execution |
| `tests/test_hierarchy.py` | offline tests |
| `scripts/count_transcript_tokens.py` | which single-pass prompts fit a context window |
| `scripts/plan_hierarchy.py` | dry-run: chunks, calls, tokens |
| `prompts/monitor_chunk_notice.txt`, `prompts/monitor_reduce.txt` | our monitor prompts |
| `vendor/monitorbench_monitor/` | upstream monitor prompt, license, manifest, README |
| `docs/plan/05-hierarchical-monitor.md` | design |
| `docs/analysis/transcript-token-counts.md` | measurements |
| `docs/research/monitor-baseline-notes.md` | what the papers and code do |
| `docs/worklog.md`, `docs/README.md` | this log, a documentation index |
| `docs/plan/06-experiment-framework.md` | plan for the reusable experiment framework (not built) |
| `docs/plan/07-design-decisions.md` | design decisions fixed before any results |
| `requirements-analysis.txt` | packages for the analysis scripts |
| `mihai/results/transcript-token-counts-20261019.json`, `mihai/results/hierarchy-plan-*-20261019.json` (three files: 32k, 131k/100k-chunk, and the pre-registered settings) | results |

Local-only, git-ignored: `rollouts_original_clean/`, `cache/tokenizer/`, `.venv/`.

### Documents changed (part 1)

See the "Changed in the repository" list in [`docs/README.md`](README.md) for the
edits to existing files and why.

### Not done (end of part 1)

- No monitor was run; `scripts/run_monitors.py` does not exist.
- No `main_only` rollouts were generated.
- No commit was made. All changes are uncommitted in the local clone.
- The cluster checkout was not updated with any of the above.

## Session 2026-10-19, part 2: commit, then Phase A

### H. Commit of the documentation

33. The user asked to commit the docs. The repository was on `main` (the default branch), so a branch `monitor-framework` was created first.
    Only `docs/`, `README.md`, `mihai/README.md` and `vendor/README.md` were staged (14 files, 1,906 insertions, 11 deletions) and committed as
    **`392288e`**, with the co-author trailer. Nothing was pushed. The code, prompts, configs and results those documents describe were
    **not** in that commit, so the committed documents link to files that exist only in the working tree; the commit message says so. The commit
    dates the pre-registration in [07](plan/07-design-decisions.md).

### I. Phase A, in the order it was done

Each step ended with tests passing before the next began. Mistakes are recorded where they happened.

34. **Facts checked before coding** (read-only): the manifest's `actor_sha256` is the SHA-256 of the file bytes (verified on the first pair);
    the system-message layout (so the hidden objective can be cut out between fixed markers); the six objective texts; and how the environments
    declare tools (`end_task` is added by the base class, the rest by an `add_tools([...])` call).
35. **`hierarchy.py` extended** (objective override, reference-plan block, partial-CoT hook, latency and token accounting, a prompt hash on every node,
    `estimate_tree_tokens` moved in from the script). The plan text is passed to `format` as an argument so braces in a plan cannot break a prompt
    (tested). 8 new tests (38 in all). `scripts/plan_hierarchy.py` was changed to use the shared estimate and reproduced its earlier output exactly.
36. **Prompts**: `prompts/monitor_plan.txt` and `prompts/monitor_plan_section.txt`, the drafts from [07 section 2.8](plan/07-design-decisions.md#28-prompts).
37. **Data layer** (`data.py`), the objective table (`configs/objectives.json`, six texts, built by `scripts/build_objective_table.py`), 17 tests, including
    against the real 41 rollouts. *Mistake:* a macOS `sed -i` call failed, which skipped the commands chained after it, so the shared test helper was not created
    and the first test run could not import it; fixed by making the rename in Python and creating the file with the editor.
38. **Registries** (`registry.py`, `configs/monitors.toml`, `configs/rollout_sets.toml`). *Caught by the strict validation:* `[monitors.qwen3-1.7b]` is read by TOML as nested
    tables because of the dot; the key is now quoted.
39. **Spec and grid** (`spec.py`), the experiment files `pilot-format-only.toml`, `baseline.toml`, `preregistered-grid.toml`, and `configs/councils.toml`. 15 tests
    (registry and spec together).
40. **Metrics and councils** (`metrics.py`, `council.py`): 23 tests, with the expected values worked out by hand in the tests.
41. **Monitor client** (`monitor_client.py`): 10 tests against a real local HTTP server. Python reported `ResourceWarning`s from the *existing* inference code, which does
    not close HTTP error bodies; harmless here and left unchanged.
42. **Tool lists** (`toollists.py`, `scripts/build_tool_lists.py`, `configs/tool_lists.json`) read with `ast`: 71, 73 and 41 tools. A cross-check against the tools the
    actor actually called found one name not in the list, `search_contacts_zelle`; inspection showed the actor invented it and the environment answered
    `ToolNotFoundError`. The extraction was right; the test encodes that exception explicitly.
43. **Freeze, strategies, costs, runner** (`freeze.py`, `strategies.py`, `costs.py`, `runner.py`, `scripts/freeze.py`, `scripts/run_experiment.py`, `scripts/score_run.py`) and a draft
    `prompts/prompts.lock.json`. 20 runner tests, later 24. *Two test bugs, not code bugs:* an assertion looked for the string `main_only` in prompts while my own synthetic
    reasoning contained a tag with that name; and one test edited a rollout without updating the manifest checksum, so verification (correctly) fired first.
44. **Comparisons** (`compare.py`, `configs/comparisons.toml`, `metrics.collapse_majority`): 9 tests. *Mistake:* my fake "oracle" monitor failed at the combining level because
    combining prompts contain only the chunk analyses, not the transcript, so it could not recognize a rollout there; the fake now carries a chunk-level detection upward, as a
    real monitor would. I also rewrote my first selector logic, which was ambiguous when several cells matched.
45. **Report** (`report.py`, `scripts/make_report.py`, `scripts/compare_cells.py`): 6 tests.
46. **Presence labels** (`presence.py`, `configs/presence_rules.json`, `scripts/presence_labels.py`): 23 tests. *The first draft of the rules (v0.1) failed an objective check*: the
    evaluator says the objectives were achieved, so the action rules had to fire, but they fired for none of 7 American Airlines malicious and none of 7 benign bank pairs
    (`\bAA\b` does not match flight numbers like `AA2847`; payments name IBANs, not people), and the rules proposed thousands of spans per rollout. Version 0.2 narrows the
    patterns, adds a structural `repeat_recipient` rule, and proposes only the earliest three matching turns per rule. Result: 446 spans over 39 positive pairs (at most 15 per pair),
    and the action rules fire for all 39.
47. **Safeguards found on review**: `--base-url` with several monitors would have pointed them all at one server, silently comparing one model with itself; the tool now refuses it,
    gained `--monitor NAME`, and warns if the served model's name does not match. That in turn showed that separate invocations would overwrite the manifest's cell list, so manifests now
    accumulate cells and sessions (2 tests).
48. **Accidental change, undone.** `chmod +x scripts/*.py` changed the file mode of three original scripts (`download_model.py`, `generate_rollouts.py`, `serve_model.py`), which git showed
    as modified. They were restored to mode 644; `git diff` on `scripts/` now shows no tracked differences. The new scripts remain executable.
49. **Dry runs on the real data.** `baseline.toml`: 984 units, 8,336 calls, 79.9 M input tokens, identical to the earlier independent calculation. The full pre-registered grid on the cached
    rollouts only: 36 cells, 11,808 units, **100,128 calls, about 1.004 billion input tokens (estimated)**, 54 plan calls. In the `action` scope 2 rollout-objective pairs (8 of 328 units)
    are single-pass without a plan but chunked with one. Results saved in `mihai/results/`.
50. **The pre-existing tests.** `requirements.txt` was installed into the local `.venv` (pydantic 2.14.1, pandas 2.3.3) and the repository's own discovery
    (`python -m unittest discover -s tests`) was run: **218 tests pass** (189 for this system, 29 original; two more runner tests were added after this entry for the `item_ids` fix, see entry 53).
51. **Documentation**: `docs/system/` (16 files) describing the built system, and corrections elsewhere, including `docs/plan/04`, which still proposed a `run_monitors.py --config
    configs/monitors.toml` whose config path is now the monitor registry. Two statements written in this part were wrong and were corrected before this entry: that plan and no-plan
    cells chunk identically (not when a transcript fits one pass only without the plan), and the annotation effort estimate (4 to 8 hours per annotator, not 2 to 5).
52. **A deviation from the session guidance:** one throwaway smoke-test directory was created under `/tmp` instead of the scratchpad; it was deleted at once. Nothing else used `/tmp`.

53. **Review fixes after the suite first passed.** (a) With `item_limit`, `score_run` expected units for *all* rollouts, so a complete pilot would have been reported
    incomplete; the manifest now records `item_ids` and scoring uses them (2 tests). (b) The report header counted the rollouts a set holds rather than those the run used; fixed
    by tagging each item with its set. (c) An end-to-end check: the real pilot experiment file was run through the real command line and the real client over HTTP against a
    throwaway fake model server (outside the repository) on the real rollouts and configs: 9 plans, 48 units in 4 cells, scored and reported, `complete` for every cell, manifest
    recording the served model, GPU record and `draft` prompts; the run directory and the server were then removed. The fake server answers by simple rules, so the numbers it produced mean nothing; the check was of plumbing.

### Verification (part 2)

* `python -m unittest discover -s tests`: 218 tests, all pass. Per module: hierarchy 38, data 17, registry and spec 15, metrics and councils 23, monitor client 10, tool lists 5, strategies 14,
  runner 24, comparisons 9, report 6, presence 23, freeze 5, original rollouts 23 and model scripts 6.
* Tests that need the real rollouts run against the 41 and skip themselves if they are absent.
* **What is verified:** the logic, against fake monitors of known behavior and hand-worked numbers; the client against a real local HTTP server; the command line's dry run on real data.
* **What is not:** nothing has talked to a real monitor model. The `reasoning_effort` request field for GPT-OSS is unverified. The plan and judge prompts have never been run on a model, so their
  wording is untested; the lock is `draft`. The objective texts have not been compared with the vendored task definitions' own text. The control rollouts do not exist.

### Files created (part 2)

| Path | Purpose |
| --- | --- |
| `monitor_experiment/{data,registry,spec,strategies,monitor_client,runner,metrics,council,compare,costs,report,presence,freeze,toollists}.py` | the system; each described under [`system/`](system/README.md) |
| `scripts/{run_experiment,score_run,compare_cells,make_report,freeze,presence_labels,build_objective_table,build_tool_lists}.py` | command-line tools |
| `configs/{monitors,rollout_sets,councils,comparisons}.toml`, `configs/experiments/*.toml` | registries and experiment files |
| `configs/{objectives,tool_lists,presence_rules}.json` | the objective table, the agent's tool lists, the draft presence rules |
| `prompts/{monitor_plan,monitor_plan_section}.txt`, `prompts/prompts.lock.json` | plan prompts and the (draft) freeze lock |
| `tests/{support,test_data,test_registry_spec,test_metrics,test_monitor_client,test_toollists,test_strategies,test_runner,test_compare,test_report,test_presence,test_freeze}.py`, `tests/__init__.py` | 189 tests |
| `docs/system/*.md` | the system documentation |
| `mihai/results/dryrun-*-20261019.json` | priced experiment files |

Local-only, git-ignored: `rollouts_original_clean/`, `cache/tokenizer/`, `.venv/`, and now `runs/`, `presence/`, `rollouts_main_only_clean/`.

### Documents changed (part 2)

See the table in [`docs/README.md`](README.md).

### Not done (end of part 2)

* No monitor model was run, anywhere. No pilot. The prompts are not frozen.
* The `main_only` control rollouts were not generated, and there is no script yet to build their manifest.
* Nothing from part 2 is committed; only the part 1 documentation is (`392288e`). Nothing was pushed.
* The cluster checkout was not updated; the SSH connection was not used in this part.
* Human annotation of presence labels has not started and needs two annotators.
* `execute`, `plan_compare`, follow-up visibility, the `structured` prompt, interrogation and HTML or figures are not implemented.

## Session 2026-10-19, part 3: commit of Phase A, annotators, Phase B preparation

The user asked: commit Phase A; explain what "annotators" means; do Phase B; keep documenting.

### J. Commit of Phase A

54. All Phase A files were staged (92 files, 16,196 insertions, 69 deletions) after checking that nothing large or unexpected was included (the largest file is 51 KB; no file-mode
    changes; nothing outside the expected directories) and committed on `monitor-framework` as **`152b414`**, with the co-author trailer. Not pushed. The working tree was clean afterwards.

### K. Annotators (an explanation, no action)

55. "Annotators" are the people who read the evidence spans that the presence rules propose and answer yes, no or unsure for each one (the protocol is in
    [07 section 2.5](plan/07-design-decisions.md#25-the-information-presence-label) and [presence-labels](system/presence-labels.md)). They are not a computing resource. Their answers
    produce the "information present or absent in the reasoning" labels behind the proposal's question of whether a monitor failed because the information was missing or because it
    missed information that was there. Two people are needed so that their agreement can be measured; the proposal's four authors could do it. It is not needed for Phase B and can wait:
    without annotators the monitors still run and every other metric is unaffected; only the "present versus missed" decomposition is lost (or reported as automatic-only).

### L. Phase B, as far as it can go without the cluster

56. **The cluster connection had expired** (`Permission denied (keyboard-interactive)`). Reopening it needs the user's passphrase and multi-factor authentication, which the assistant cannot
    supply, so **no cluster command was run in this part**. Everything that could be prepared and tested locally was.
57. **Decisive local check.** Hashing the `monitor_experiment/*.py` files of commit `5dc0417` reproduces the cached batch's recorded `runtime_implementation_hash` (`8542b29e…`) exactly; the two
    earlier commits and the framework branch do not. This confirms that the control rollouts must be generated from a pristine `5dc0417` checkout (the clean one on the cluster) and not from this
    branch. (A first throwaway command in that step had a typo and errored harmlessly; the result is from the second.) A test now reproduces it.
58. **`collection_builder.py`, `scripts/build_collection.py`**: turns a rollout cache into a verified collection in the same layout as the cached batch, keeping a sample only if its actor and
    follow-up completed (never by outcome), with exclusion reasons, byte-copy checks and agreement checks on generation settings, implementation hash and model revision. 6 tests, using
    the real rollout generator with a scripted client so the cache layout under test is the real one (they take about 10 seconds because the real environments are loaded). This replaces the
    cluster-only script that built the original manifest, which is not in this repository.
59. **Registry change:** an optional `reasoning_parser` field (`qwen3` for the five Qwen3 entries; unset for GPT-OSS and Gemma because the right name was not verified). It is part of a
    monitor's identity, which changes every cell ID relative to part 2; no results existed to be affected.
60. **`monitor_serving.py`, `scripts/serve_monitor.py`**: builds the vLLM command for one registered monitor (served under its registry name so the runner's served-model check recognises it;
    BF16 for Qwen3, `--dtype auto` otherwise; YaRN only on request and required above the native 32,768; no tool-calling flags), refuses a context below what the registry promises, a placeholder
    monitor or a non-model directory, and records the command, vLLM version and monitor identity. 7 tests.
61. **`control_setup.py`, `scripts/prepare_controls.py`**: a private model directory of symlinks to the shared weights with an identical copy of the download manifest (because the serving script
    writes a manifest into the model directory); a control config derived from the cached batch's by two exact text edits (variants and sample count; all other settings asserted equal in a test);
    verification that a checkout is the expected commit, unmodified and has the cached batch's implementation hash; and a worker plan covering every requested sample exactly once. 11 tests.
62. **Cluster scripts** (`mihai/cluster/setup_cluster.sh`, `run_controls.sbatch`, `run_monitor.sbatch`), modeled on the existing, proven `run_qwen.sbatch`. Deliberate differences: every path is a
    variable defaulting to the user's own directory; **nothing is written under the teammate's directory** (enforced by a test that scans the scripts); the original's `setfacl` permission changes
    for teammates are omitted; the checkout identity is verified before serving; the controls are served with the cached batch's arguments (one GPU, 131,072 context, YaRN 4). 7 smoke tests (syntax,
    fail-fast, no writes to the shared directory, default directory, the identity protections). The scripts cannot be run here.
63. **A conflict with the pre-registration was found and fixed.** The pilot is supposed never to load labels (so wording cannot be tuned to detection), but the monitor job scored every run. The job now
    takes `SCORE=0`, and a new `pilot.py` / `scripts/pilot_summary.py` writes a label-free summary (validity, retries, finish reasons, reply and plan lengths, prompt sizes against the input limit, latency,
    throughput) from `items.jsonl`, `nodes.jsonl` and `plans/` only. A test checks that the module cannot reach labels. 4 tests.
64. **Documentation**: `docs/system/cluster.md` (what is known, the layout, the runbook B1 to B5, what is not verified) and `docs/system/collections.md`; updates to the system README, CLI page, registries page,
    the plans' status tables, the decisions document (the identity check), the index and README. *A mistake in the documentation step:* my first edit script aborted on one non-matching string before writing
    anything (each file is written only after all its edits match, so nothing was half-applied); it was corrected and rerun.

### Verification (part 3)

* `python -m unittest discover -s tests`: **253 tests, all pass** (224 for this system, 29 original). New in this part: collection builder 6, control setup 11, monitor serving 7, pilot 4, cluster scripts 7.
* Verified: the implementation-hash reproduction for `5dc0417` against the real cached manifest; the collection builder against the real generator's cache; every script parses as bash.
* **Not verified, because the cluster was unreachable:** any Slurm option (partition, account, GPU resource name, time limit are unknown); that the shared environments run vLLM under your account on a compute node;
  `pip install` on a login node for the analysis environment; the vLLM flags for GPT-OSS and Gemma; the `reasoning_effort` field; real generation speed; that control transcripts resemble the cached ones.

### Files created (part 3)

`monitor_experiment/{collection_builder,control_setup,monitor_serving,pilot}.py`; `scripts/{build_collection,prepare_controls,serve_monitor,pilot_summary}.py`;
`mihai/cluster/{setup_cluster.sh,run_controls.sbatch,run_monitor.sbatch}`; `tests/test_{collection_builder,control_setup,monitor_serving,pilot,cluster_scripts}.py`;
`docs/system/{cluster,collections}.md`.

### Not done (end of part 3)

* Nothing was run on the cluster, so: no sync of the branch, no setup, **no control rollouts**, no pilot, no monitor served, no baseline.
* The Phase B preparation (this part) is **not committed**; only Phase A (`152b414`) and the part 1 documentation (`392288e`) are.
* No monitor model has been run anywhere. No human annotation. Prompts remain `draft`.
* To continue: the user reopens the SSH connection (passphrase and MFA), and supplies or helps find the Slurm options for an H200 job.

## Session 2026-10-19, part 4: Phase B on the cluster

The user reopened the connection, pointed to the YCRC job-scheduling tutorial and asked for the Phase B preparation to be committed. Everything in this part ran on Bouchet
(`login2`) unless stated. Times are UTC as recorded in job status files.

### M. Commit and Slurm facts

65. **Committed the Phase B preparation** as `af32c0d` on `monitor-framework` (29 files, 1,536 insertions; audit showed nothing unexpected and no mode changes). Not pushed.
66. **The Slurm tutorial** (<https://docs.ycrc.yale.edu/clusters-at-yale/job-scheduling/>, read through a page-summarising tool) gives the general options (`--account`, `--partition`, `--time`, `--gpus`,
    `--cpus-per-task`, `--mem`), the commands (`sbatch`, `squeue --me`, `scancel`, `sacct`, `sbatch --test-only`) and the rule not to run heavy computation on login nodes. It does not name GPU
    types or partitions for this cluster, so those were read from the cluster itself.
67. **Facts established on the cluster by read-only commands:** the account is `cpsc4880` (QOS `normal` and `interactive`); `gpu_h200` allows all accounts and QOS `normal`, with no maximum time; there are also
    `gpu_h100`, `gpu_b200`, `gpu_rtx6000`, `gpu`, `gpu_devel` partitions; storage is 4.0 TB with 3.2 TB free on `/nfs/roberts/project`; `pip install` works from the login node.
68. **The teammate's job records are readable** (`$SHARED/logs/*.submission.json`). They give the exact flags of the successful H200 job: `--account=cpsc4880 --partition=gpu_h200 --nodes=1 --ntasks=1
    --gpus=h200:1 --cpus-per-task=8 --mem=96G --no-requeue` (24 h limit). That job (29894244) started 20:36Z, had its server ready after 2 minutes and ended 22:51Z: **30 pairs in about 2¼ hours**,
    much faster than my earlier assumption of 5 pairs an hour. The 2×A40 job (29860690) ran the full 6 hours and was stopped. The record's configuration hash for the cached batch's config,
    `35988863…`, equals the hash of `mihai/configs/rollouts-output-32768.toml` on the cluster: the source config is the one that was used.
69. **The odd start estimates are explained.** `sbatch --test-only` reported a start time of exactly one year ahead for every GPU partition. A reservation named `EmergencyMaintenance` (365 days, for admins)
    covers a set of nodes; the estimate is that reservation's end, not a real queue time. The jobs below started within seconds. The queues are long (hundreds of jobs pending in each GPU partition) yet
    free GPUs existed, so the real behaviour was only learned by submitting.

### N. Setting up and verifying (no GPU)

70. **B1: copied the branch** to `$ME/monitor-framework` with `rsync` (149 files, 1.1 MB, 3 minutes), leaving out `.git`, the environment, data, `vendor/monitorbench_agent` and the large test assets.
71. **Setup script** (`setup_cluster.sh`, 18 minutes on the slow filesystem, exit 0). Verified by its own checks: the private model directory has all 17 files (29,552,612,206 bytes, revision `40c06982…`);
    the data links exist; the derived config differs from the cached batch's in exactly the two intended lines (a diff confirmed this); **the pristine checkout is commit `5dc0417`, clean, with implementation hash
    `8542b29e…`, equal to the cached batch's**; the analysis environment installed (PyYAML, tokenizers, pydantic, pandas).
72. **Environment self-test** (`generate_rollouts.py --check-environments`, 12 s): the three environments load and register **71, 73 and 41 tools**, independently confirming the `ast`-based tool lists.
73. **The framework on the cluster:** the freeze lock shows no differences and the tokenizer's SHA-256 equals the local file's; a dry run of the pilot file priced 48 units, 352 calls and 9 plan calls.

### O. Jobs submitted

74. **Control rollouts: job 30068171** (`controls-main-only`). `sbatch --parsable --account=cpsc4880 --partition=gpu_h200 --nodes=1 --ntasks=1 --gpus=h200:1 --cpus-per-task=8 --mem=96G --time=08:00:00
    --no-requeue --output=$ME/logs/controls-%j.log --chdir=$ME/monitor-similarity-experiment mihai/cluster/run_controls.sbatch`. A receipt with the command, generating commit, config and launcher hashes was written to
    `$ME/logs/controls-30068171.submission.json`. It started within 20 seconds on `a1122u11n01` (3 minutes after the 23:03Z start the server was ready; six workers began generating).
    Config hash `b844b551…`. Time limit 8 hours (ends 03:03Z), reduced from the teammate's 24 because the earlier comparable job needed about 2¼ hours.
75. **Format-only pilot: job 30068179** (`pilot-format-only`), Qwen3-14B as the monitor, `SCORE=0` so no label is read, 3-hour limit. It showed `ReqNodeNotAvail, Reserved for maintenance` for a few seconds and then
    started on the same node (a different GPU). A receipt is in `$ME/logs/monitor-30068179.submission.json`.

### P. The format-only pilot and the freeze

76. **The pilot finished** (job 30068179, exit 0, 911 seconds of run time, started 23:06:55Z; server ready after 85 s). Qwen3-14B as the monitor, scopes `action` and `cot`, contexts `none` and `plan`, one rollout of each task and
    variant, one sample: 48 units, 352 requests. Read through `scripts/pilot_summary.py` only, which cannot reach labels; the job ran with `SCORE=0` and the run directory contains no `metrics` files. **Results:**
    0 invalid requests, 0 retried, every reply a normal stop; completion tokens per request median 997 (95th percentile 1,698, max 3,189 against a 16,768 cap); prompts up to 14,243 tokens against the 15,488 limit; 9 plans of
    330 to 474 words (524 to 870 tokens) with no retry; chunks per unit median 6, max 23; request latency median 15 s; **405 completion tokens per second at concurrency 8**. The planning assumption of about 1,000 tokens per
    reply was accurate.
77. **Qualitative format check** (no labels): one plan and two replies (a chunk reply and a combining reply) were read. The plan has numbered steps with tools and checks; the replies follow the requested three-part structure
    and quote evidence with turn numbers. Nothing refused or looked malformed.
78. **An observation, deliberately not acted on.** Across the nine plans, all mention actions that are unneeded, unusual or to be avoided (2 to 6 phrases each) but only two give them the dedicated heading that item 3 of the
    plan prompt asks for. The pre-registered rule permits wording changes only to fix format failures; none occurred, so the wording was left unchanged. It is recorded as a question for the user.
79. **A design flaw in my freeze mechanism, found before freezing.** Cell IDs included the hashes of the councils file, the comparisons file and the presence rules, none of which changes what a monitor says; editing a comparison
    or revising a presence rule would have invalidated every monitor output. Fixed before any confirmatory run exists: cell IDs now cover the five prompt files, tool lists, objective table and tokenizer; the freeze lock
    additionally covers the councils and comparisons files; and the presence rules have a separate lock, because they must stay editable until the annotator agreement check. Recorded as **amendment A5** (no monitor result had
    been seen). 5 new tests, including one showing an analysis-file edit changes the lock but not a single cell ID. The 258-test suite passes.
80. **The prompts were frozen**: `freeze.py write --status frozen` (7 files, tool lists, objectives, tokenizer `aeb13307…`), and `freeze.py rules-write --status draft` for the presence rules (version 0.2). The wording
    of every prompt is exactly what the pilot ran, except that the pilot ran under the older fingerprint scheme (cell IDs differ; the prompt files do not).
81. **Documentation** updated with the Slurm facts, the pilot table and the corrected freeze design (`docs/system/freeze.md` rewritten, `cluster.md`, plan status tables, indexes, counts: 258 tests, 229 new).

### Q. Control rollouts, as of this entry

82. Job 30068171 had 3 complete samples cached after 22 minutes (6 workers). At that rate (about 8 an hour) the 36 requested samples would need about 4½ hours, inside the 8-hour limit (ends 03:03Z); the earlier
    comparable job ran 12 an hour. Not yet complete.

### R. A flaw in the control job's design, found while it ran

83. **Worker 0 of job 30068171 died after one sample.** About 27 minutes in, its log ended with `ProtocolError: Unclosed reasoning block; likely truncated generation` (the model's response ran into the 32,768-token limit inside
    its reasoning, an ordinary execution failure of the kind that cost the cached batch 7 of 48 samples). The generator **stops its whole process** at the first execution failure, and my job gave each of six processes a block of six samples,
    so the other five samples of that block (bank, samples 1 to 5) would never have been attempted. With roughly one sample in seven failing, most blocks would have been cut short and the target of 8 retained per task missed.
    The teammate's pipeline ran each pair as its own invocation for this reason; I had not carried that design over. The mistake was mine: the block design was written and only smoke-tested without being run.
84. **Fix, with tests.** `scripts/run_pairs.py` runs one process per (task, sample), eight at a time, skips samples already complete in the cache under any serving identity, writes one log per pair and a `summary.json`,
    and fails only if *every* attempt fails. The collection builder now **refuses** to choose silently if one sample has two complete entries (the same sample generated under two serving identities). 8 new tests; `run_controls.sbatch` now calls the
    driver; the old `prepare_controls.py workers` plan is no longer used by the job. 266 tests pass.
85. **Cost of the fix.** The in-flight rollouts of job 30068171 are lost when it is cancelled (about 27 minutes of five concurrent samples); the five completed samples (american_airlines_2 samples 0 and 6; spam_filter_update samples 0, 6 and 7)
    stay in the cache and are skipped by the new job.
