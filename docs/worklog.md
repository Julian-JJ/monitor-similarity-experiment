# Work log

A factual record of what was done, in order, including mistakes and actions the
user declined. Newest session last. Times are omitted except where a file's own
timestamp matters. "Local" means the Mac at `/Users/arushsrivastava/Desktop/VS Workspace`;
"cluster" means Yale's Bouchet (`bouchet.ycrc.yale.edu`).

## Session 2026-10-19

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
    [Verification](#verification).

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
    [Documents changed](#documents-changed).

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

### Verification

- `tests/test_hierarchy.py`: 30 tests, all pass locally (`.venv/bin/python -B -m unittest tests.test_hierarchy`).
  They include a check that every one of the 41 saved rollouts yields a clean hidden
  objective; that test is skipped when the rollouts are absent.
- The pre-existing tests (`tests/test_rollouts.py`, `tests/test_model_scripts.py`) were
  not part of this work and were not changed. See the item above about running them.
- No monitor model was run, on the cluster or locally. Nothing in this log is a
  monitorability result.

### Files created

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

### Documents changed

See the "Changed in the repository" list in [`docs/README.md`](README.md) for the
edits to existing files and why.

### Not done

- No monitor was run; `scripts/run_monitors.py` does not exist.
- No `main_only` rollouts were generated.
- No commit was made. All changes are uncommitted in the local clone.
- The cluster checkout was not updated with any of the above.
