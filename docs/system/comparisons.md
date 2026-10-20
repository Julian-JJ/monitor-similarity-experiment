# Comparisons

Code: [`monitor_experiment/compare.py`](../../monitor_experiment/compare.py). Pre-registered list: `configs/comparisons.toml`
(P1 to P5, [07 section 3](../plan/07-design-decisions.md#3-analysis-rules)). Tests: `tests/test_compare.py` (9, with fake monitors that are an oracle,
always-detect, never-detect and half-detect, so every outcome is known in advance).

## Writing a comparison

A comparison names its two sides by **settings**, not cell IDs, so the file can be written before any run exists:

```toml
[[comparisons]]
id = "P4 plan vs none (qwen3-4b)"
a = { monitor = "qwen3-4b", task_context = "plan" }
b = { monitor = "qwen3-4b", task_context = "none" }
# optional: per = ["scope"] (default), fixed = { hierarchy = "long-context" }
```

For each value of the `per` settings (by default each observation scope) the sides are resolved to cells. Settings not given take
`DEFAULT_FIXED`: `task_context none`, `hierarchy upstream-limits`, `partial_cot off`, `reasoning default`. A side matching zero or several cells is an error
for that comparison, which is then **reported as skipped with the reason**, never dropped.

Special monitors on a side:

* `council:<name>` builds the council's verdicts from the member monitors' stored verdicts (primary rule: majority) for the same settings.
* `best_member_of:<name>` picks the council member with the best pooled point estimate of the primary metric on the same data. Choosing the best on the same
  data favours the member, so beating it is conservative for the council.

## What is computed

For each resolved comparison: the paired difference of the primary metric (A − B) and of recall with bootstrap intervals ([metrics](metrics.md)),
the outcome (`A better`, `B better`, `no clear difference`, `mixed`, `undefined`), and the Holm-adjusted p-value. **Holm is applied within each
observation scope** across all comparisons sharing it, as pre-registered. If the two sides have different numbers of samples per pair (the same-model
control gives one decision per pair), both are collapsed to one majority decision per pair and the result carries a note.

`scripts/compare_cells.py runs/NAME [runs/OTHER ...]` writes `comparisons.json`; `make_report.py --comparisons` includes it.

## Notes

* Only comparisons in the file are confirmatory. Anything else is exploratory and the report should say so.
* The runs given must contain the cells; a comparison needing a monitor that was not run is skipped.
* A council needs all its members to have been run with identical settings and the same rollouts.
