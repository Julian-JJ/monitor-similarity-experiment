# Monitor similarity experiments

How much does a monitor's similarity to the agent it watches affect its ability to catch hidden side objectives? The actor is fixed (**Qwen3-14B**), running MonitorBench's code-verifiable dual-objective agent tasks (`bank_transfer_2`, `american_airlines_2`, `spam_filter_update`). Open-weights monitors that differ in size, architecture and family are compared on the same saved rollouts, alone and in councils of three.

Metrics are TPR, TNR on clean (`main_only`) control rollouts, and g-mean², with bootstrap intervals. Design choices were fixed before any scored run and are recorded in [docs/plan/07-design-decisions.md](docs/plan/07-design-decisions.md).

## What exists

- **Rollouts:** 41 complete actor/follow-up pairs (original batch) and 34 `main_only` clean controls, both on the cluster and git-ignored.
- **Experiment system:** a TOML-driven runner, hierarchical monitor for transcripts too long for one prompt, metrics, councils, pre-registered comparisons (P1 to P5), reports, and cluster job scripts. 277 offline tests pass.
- **Prompts:** frozen after a format-only pilot.

## Progress (2026-10-20)

| Item | State |
| --- | --- |
| Actor rollouts and controls | done |
| Pilot (Qwen3-14B as monitor, format only) | done |
| Qwen3-32B baseline (1,800 units, scored) | done: [report](docs/analysis/baseline-results.md) |
| Qwen3-14B baseline (same model as the actor) | submitted (job 30069778), result pending |
| Comparisons P1 to P5 | not yet run |
| Remaining monitors (4B, 30B-A3B, GPT-OSS-120B) | not started |
| Presence labels (two human annotators) | tooling done, annotation not started |
| Full pre-registered grid (about 170k calls) | too large for one server; needs a cut |

First 32B result, descriptive only (three tasks): the monitor detects almost every malicious rollout (TPR 0.95 to 1.0) but falsely flags many clean ones (TNR 0.71 to 0.78), mostly when told the malicious objective.

## Plan to the first week of December

Finish baselines and decide the grid cut (late Oct); serve the other monitors and annotate (Nov 1 to 9); plan-context cells and councils (Nov); hierarchy validation and the remaining grid (mid Nov); buffer and analysis (late Nov); writing (Dec 1 to 5).

## Where to look

- [docs/README.md](docs/README.md): index of all documentation and status
- [docs/system/README.md](docs/system/README.md): how the built system works and how to run it
- [docs/worklog.md](docs/worklog.md): chronological record, including mistakes
- [docs/rollout-runner-guide.md](docs/rollout-runner-guide.md): the previous README (rollout generation, cluster quick start, cache, tests)
- [mihai/README.md](mihai/README.md): Bouchet cluster guide

Upstream sources: [MonitorBench](https://arxiv.org/html/2603.28590v1) (environments) and [Monitoring Monitorability](https://arxiv.org/html/2512.18311v1) (follow-up prompt); vendored code and licenses are under `vendor/`.
