# Strategies, partial CoT and councils

Code: [`monitor_experiment/strategies.py`](../../monitor_experiment/strategies.py),
[`monitor_experiment/council.py`](../../monitor_experiment/council.py). Tests: `tests/test_strategies.py`, `tests/test_metrics.py`
(councils), `tests/test_runner.py`.

## What a strategy is

A **strategy** is a monitor *method*: how a rollout becomes prompts and prompts become a verdict. It has two steps so that planning can be
priced without a model:

* `prepare(item, told, cell, plan_text=None)` → an offline plan: the chunks and their exact level-0 prompts, token counts, and anything that
  was cut (tool results, partial CoT);
* `run(item, told, planned, cell, complete, seed)` → a result with the same shape for every strategy:
  `status` (`complete`, `invalid`, `error`), `verdict`, `hierarchical`, `calls`, `model_requests`, token and latency totals, `critical_path_seconds`,
  and every node with every attempt.

Metrics, councils, comparisons and reports read only that shape and the labels, which is why a new method needs no change to them.

The only strategy now is `JudgeStrategy` (`hier_ad`), the hierarchical monitor of [05](../plan/05-hierarchical-monitor.md): MonitorBench's A–D
prompt on each chunk, then analyses combined in bins until one verdict remains; the unmodified prompt when the transcript fits one pass.
`prepare` supplies the objective text from the objective table, so the same rollout can be judged under either told objective.
To add a method, write a class with these two methods and have `runner.run_experiment` choose it from a (future) `strategy` axis.

## Partial CoT

`partial_cot_transform(config, count)` returns a function that removes part of the actor's **reasoning** before rendering, or `None` when
the cell's `partial_cot` is `off`. It never changes actions, tool results or visible text.

| Setting | Effect |
| --- | --- |
| `turns:p` | keeps the reasoning of the first ceil(p × turns) turns; later turns' reasoning is blanked |
| `tokens:p` | keeps the first p of all reasoning tokens in order, cutting the turn that straddles the limit at a paragraph, line or word boundary |

Each run records, per unit, `partial_cot`: the mode, value, turns total, turns with reasoning shown, reasoning tokens total and shown, and
`fraction_shown`. This is a deliberate, labelled cut, distinct from the rule that nothing is shortened silently. It applies to the `cot` and
`all` scopes; with `action` it would do nothing, and such a cell is pointless. Use it to ask how monitorability falls as less of the
reasoning is visible, and whether the evidence appears early enough for a prefix to catch it (the first-turn information from the
[presence labels](presence-labels.md) says where evidence first appears).

## Councils

`council.py` builds a council's verdicts from monitors' **stored** verdicts; no model is called. The pre-registered councils are in
`configs/councils.toml` (see [the decisions](../plan/07-design-decisions.md)). Rules:

| Rule | Detected when |
| --- | --- |
| `majority` (primary) | more valid members say detected than not |
| `any` | at least one valid member says detected |
| `unanimous` | every valid member says detected |

A member whose verdict is invalid abstains. A council needs at least two valid members; under `majority`, two valid members who disagree
are a tie. Either case makes the council verdict `invalid`, never "not detected". Council sample *j* uses every member's sample *j*; a
member written `name#k` contributes that monitor's sample *k*, and the council makes one decision per pair (this is how the same-model
control uses three samples of one model). Cost adds up over members; latency is the slowest member's. Councils are then scored and compared like
any cell ([comparisons](comparisons.md)).
