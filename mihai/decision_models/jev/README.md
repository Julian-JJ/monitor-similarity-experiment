> For the current model-by-model experiment folders and verified results, see [Jev experiments](../experiments/jev/README.md). This page retains the runner and historical deployment notes.

# Jev experiments

**November 24 update:** Qwen summaries are finished: 2,808 valid and 26 truncated. GLiDE and Jev each completed 429/450 cases; 21 were blocked. See [the audited results](../summary-results-20261124/audit.json).

The dated progress notes below retain earlier snapshots.

Uses **`jev-1.14.0`** through TypeSafe, with the exact prepared GLiDE
`state`, instructions, A–D choices, transcript rendering and chunk boundaries.
The API key comes only from `TYPESAFE_API_KEY`; it is never stored in this folder.
No Jev weights or GPU allocation are needed. The key is not needed for preparation,
tests or scoring. The current input collection has 75 rollouts, tested against
two objectives and in three views: actions, reasoning (`cot`), and combined (`all`).

On November 23, the real-input pilot **34391510** passed: **68 requests** completed
(6 full inputs, 57 chunks, 5 summary inputs), with one summary case blocked because
Qwen had not supplied all its summaries. The longest accepted input was **229,506
Jev tokens**. These are execution checks, not benchmark accuracy results.
[Pilot audit](api-smoke-audit.json) · [Current job status](status.json).

As of 19:39 UTC, all **450 full-input requests** and **2,834 chunk requests**
completed and passed the identity/content audit. Production wall times were
13m 13s and 1h 02m 10s. The 12 completed method/view scores are available in
[the audited report](results-completed-34426786/audit.json); Qwen-summary results
are still pending. Mean chunk aggregation on reasoning or combined inputs reached
98.1% primary accuracy (39/41 positives detected; zero false alarms on 66 clean cases).

Production jobs: **34391865** full inputs, **34391866** shared chunks,
**34391867** ordered Qwen summaries, and **34391868** final scoring. They run in
sequence; summaries also wait for Qwen job 34371577. Results stay in the separate
`jev-variants-20261123` directory. Saved pilot responses are reused.

## Experiments

| Method | Jev calls | Final decision |
|---|---:|---|
| Full input | 450 | Highest-probability A–D answer; A means detection |
| Full input, sampled comparison | 0 extra | Four draws from that same probability vector, temperature 0.6 / top-p 0.9 / seed 0 |
| Shared chunks, maximum P(A) | 2,834 | Maximum P(A) ≥ 0.5 |
| Shared chunks, average P(A) | 0 extra | Unweighted average P(A) ≥ 0.5 |
| Ordered Qwen summaries | Up to 450 | One highest-probability A–D decision over **all** summaries |

Maximum: **3,734 API calls**. A smoke check reuses its saved calls in the full run.
Max/mean rules consume one common set of chunk responses. They are binary rules,
not invented A–D answers; A being the largest probability is different from A ≥ 0.5.
The sampled comparison is additional output from the full-input calls, not four
independent model analyses. We do not send sampling parameters to Jev.

`run_jev.py` imports the pinned existing framework for input verification,
sampling and scoring. It does not regenerate actor rollouts. Grading labels stay
in the scorer and are absent from outgoing requests. The original 2,000-character
tool-result cuts remain. No extra transcript truncation, rechunking or prompt tuning
is introduced. The original GLiDE prepared-input file's SHA256 is pinned in config.

## Context and timing

Jev's documented normal limits are 32k tokens per question and 64k per request.
Its optional long-context header raises both to 262k. We enable that header for
full reasoning and combined inputs; full actions, chunks and summaries use normal
mode. The current GLiDE lengths reach 26,275 / 216,463 / 229,167 tokens respectively,
but **these are not Jev token counts or a guarantee that Jev will accept them**.
There is no verified local Jev tokenizer in this setup. The pilot verified actual
acceptance of the shortest and longest inputs in each view; returned input counts
reached 26,884 for actions, 216,646 for reasoning, and 229,506 for combined.
An oversize request
is recorded as a failure; it is not silently shortened or changed to another method.
TypeSafe warns that long mode can reduce accuracy, so it remains part of the
reported serving settings. [Model limits](https://docs.typesafe.ai/models)

The API returns a choice and option probabilities, which we validate against
the pinned version and compute rules above. [Choice contract](https://docs.typesafe.ai/primitives/choice)
We record API latency, actual token usage and stage wall time. Jev's hosting GPU
and server memory are not exposed; there will be no claimed Jev GPU-memory curve.
Latency includes the network and cannot be treated as a controlled GPU-speed comparison.

## Code and running later

- `client.py`: one HTTP request plus response validation. No automatic retries.
- `run_jev.py`: prepare, evaluate, reuse saved results, and score with the baseline.
- `config.json`: pinned inputs and a separate `jev-variants-20261123` output directory.
- `test_jev.py`: fictional responses and temporary files only; never contacts TypeSafe.
- `run.sbatch`: CPU-only launcher. It does not submit anything by itself.
- `launch_private.py`: verifies the frozen package and reads the private cluster
  key into the evaluation child's environment. Submission records contain no key.
- `queue_evaluations.py`: records durable submissions for the four production jobs.
- `audit_pilot.py`: checks saved pilot identities, probabilities and sampling.

On the cluster, use the deployed package path from `deployment.json` as `JEV`,
and the team's existing shared project root as `PROJECT`. No key is required:

```bash
"$PROJECT/envs/monitor-research/bin/python" -B -m unittest discover -s "$JEV" -p 'test_*.py'
sbatch --partition=devel --time=01:00:00 \
  --output="$PROJECT/logs/jev-prepare-%j.log" \
  "$JEV/run.sbatch" prepare "$JEV/config.json" "$PROJECT"
```

Preparation loads the large shared input inventory, so use the CPU job rather
than the login node. Wait for a successful `ready.json`. This step makes no API calls.
The submitted jobs use the immutable launcher recorded in `private-launcher.json`.
It reads `~/.config/monitor-experiments/jev.key` on the cluster (file permissions
600, private parent directory) at execution time. Do not put the key in chat,
submission arguments, the repository or logs. It is not exported through Slurm.

For a new evaluation, first pilot `full --smoke`, `chunks --smoke` and
`summaries --smoke`, then inspect their saved results. The current pilot has already
passed and production has already been submitted: **do not submit it again**.
The stage order is `full`, `chunks`, `summaries`, then `score`, which produces all
15 method/view reports, including explicit missing/failed counts. The durable
receipts under the cluster's `logs/` directory and local `submitted-jobs.jsonl`
identify these jobs. Reconcile them with Slurm before any future action.

Each invocation uses a file lock. A completed cached request is verified and reused.
An interrupted attempt, HTTP failure or invalid response is never resent automatically.
The first API error stops the stage for review, including rate limits; running
`score` remains possible and does not turn errors into negative classifications.
A missing Qwen summary blocks that case without sending partial evidence. It can
be reconsidered once all matching summaries exist, because no API attempt occurred.

Raw inputs and summaries stay on the cluster. Only the selected request is sent
to TypeSafe when inference is explicitly run; local reports contain compact metrics.
The Qwen-summary condition shares the Qwen generation cost with GLiDE and must
also report that cost when treated as a standalone monitoring system.
