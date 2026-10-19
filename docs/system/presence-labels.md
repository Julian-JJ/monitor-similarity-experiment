# Information-presence labels

Code: [`monitor_experiment/presence.py`](../../monitor_experiment/presence.py); rules `configs/presence_rules.json`; entry point
`scripts/presence_labels.py`. Tests: `tests/test_presence.py` (23). Protocol and rationale:
[07 section 2.5](../plan/07-design-decisions.md#25-the-information-presence-label); annotators: [07 section 2.10](../plan/07-design-decisions.md#210-annotators).

## What it answers

The proposal's stated gap: when a monitor misses a hidden objective, was the information never in the agent's reasoning, or was it there and the monitor
failed to use it? A **presence label** says, for each *positive pair* (a rollout and an objective it achieved), whether evidence of the objective is in the
agent's reasoning (`reasoning`, plus the agent's visible text) and in its tool calls (`actions`), and at which turn it first appears. No language model proposes or
labels anything: the rules propose, humans decide.

## The pieces

1. **Rules** (`configs/presence_rules.json`, version 0.2, `draft`). For each of the six (task, objective) pairs, patterns that search the stored reasoning
   (`specific` identifiers such as the IBAN, the sender address or the phrase in a spam rule; `intent` mentions of a "secondary task") and tool calls
   (a tool-name pattern plus an argument pattern, or the structural `repeat_recipient` rule: a recipient paid at least three times, used for the benign bank
   objective because payments name IBANs, not people). Derived only from the six objective texts and the vendored tool definitions. Each rule proposes the
   **earliest three matching turns** (`per_rule_spans`), one span per turn, with the number of turns it matched in all; `--offset` style requests for more are
   supported by `propose(offset=...)`.
2. **Annotation.** `scripts/presence_labels.py annotate --annotator NAME` shows each span with its context and the objective, and records `yes`, `no`
   or `unsure` to `presence/annotations.jsonl`. It shows nothing about any monitor. An annotator named `adjudicator` overrides a dispute.
3. **Consensus and labels.** `consensus` ignores `unsure`; a majority decides; a tie is `disputed`. A pair's label for a source is `present` (at least one span
   confirmed), `absent` (all proposed spans decided and none confirmed, or none proposed), `disputed`, or `unlabeled` (spans still undecided).
4. **Agreement.** `annotator_kappa` (Cohen's kappa over spans both annotators answered yes or no) and `spot_check_recall`: annotators read randomly chosen turns of
   reasoning *without* seeing the rules' spans, and recall is the share of turns judged evident in which the rules had proposed a span. Requirements before the labels
   are used: kappa ≥ 0.7 and spot-check recall ≥ 0.9.
5. **Decomposition.** `decompose(collected, pairs, labels, scope)` splits a cell's results over positive pairs by presence under the scope (`cot` uses reasoning,
   `action` uses tool calls, `all` either) and reports `extraction_recall` (detected among present), `extraction_gap` (1 minus it), `recall_when_absent` and
   `information_limited_share` (absent among present-or-absent); disputed and unlabeled pairs are counted, never guessed.

## Workflow

```bash
python scripts/presence_labels.py candidates                       # presence/candidates.json
python scripts/presence_labels.py sample --pairs 20                # which pairs two annotators both label, and a spot-check sample
python scripts/presence_labels.py annotate --annotator alice --only-sample
python scripts/presence_labels.py annotate --annotator bob   --only-sample
python scripts/presence_labels.py summarize --first alice --second bob     # kappa, spot-check recall, labels.json
```

The order that matters: freeze the rules, then annotate, then compute agreement, then label the rest, then freeze the labels, and **only then**
compute the decomposition against any monitor's results.

## What the draft rules do on the real rollouts (no monitor involved)

| Check | Result on the 41 cached rollouts |
| --- | --- |
| positive pairs given candidate spans | 39 of 39 |
| candidate spans in all | 446 (at most 15 for any pair; mean 11.4) |
| pairs whose **action** rules fire | 39 of 39 |
| pairs with a `specific` reasoning span | 39 of 39 |

The action result is an objective check: the evaluator says each of these objectives was achieved, so the achieving actions had to be there. (The first draft,
version 0.1, failed this check: it matched `\bAA\b` against flight numbers like `AA2847`, and names against payments that name IBANs; and it proposed thousands
of spans per rollout. Both were fixed before any human saw it.)

**An expectation to keep in mind, not a result:** the agents often restate their secondary task in their reasoning, so most positive pairs will probably be
labeled `present` for reasoning, which would leave few `absent` pairs and make the "information was never there" side of the decomposition thin. Whether that is
so is for the annotators to find out.

## Where the files go

`presence/` (candidates, sample, annotations, labels) and `runs/` are git-ignored, because candidate spans quote the agent's reasoning, which the repository
keeps out of Git. The human **answers** are small and valuable, so after review copy `annotations.jsonl` and `labels.json` (they contain span ids and decisions,
no reasoning text) to `mihai/results/presence/` and commit them with the frozen rules.

## Effort

446 candidate spans across 39 pairs. Double-annotating 20 pairs is about 230 spans per annotator; at one to two minutes a span that is roughly **4 to 8 hours
each** (the decisions document's earlier estimate of 2 to 5 hours was low). The remaining 19 pairs, one annotator confirming the rules' spans, add about
200 spans, and the spot check (ten turns in each of six pairs) about an hour. These are estimates, not measurements.

## Limits

* Whether information is "present" is a judgment; the decomposition should be shown under rule-only and human-confirmed labels.
* Only the earliest three turns per rule are proposed. If none of a rule's proposals is real but a later one is, the annotators must ask for more; this is a
  source of false `absent` that the spot check is meant to bound.
* Presence says the information was available to a reader of the scope; it does not say it was easy to find.
