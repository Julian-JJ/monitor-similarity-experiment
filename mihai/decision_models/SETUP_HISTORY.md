> Historical setup instructions and dated run notes. For current results and completed status, see [the experiment index](README.md).

# Decision-model setup

**November 24 update:** Qwen summaries are finished: 2,808 valid and 26 truncated. GLiDE and Jev each completed 429/450 cases; 21 were blocked. See [the audited results](summary-results-20261124/audit.json).

The dated progress notes below retain earlier snapshots.

GLiDE is installed and passed a GPU smoke test and two synthetic demo cases on
2026-11-15. See [installation details](installation.json) and the exact
[demo inputs and outputs](demo_output.json). The actions-only evaluation below
reuses the baseline framework. The [Jev comparison suite](jev/README.md) passed
offline checks and a 68-request real-input pilot; production evaluations were
launched on November 23. Full-input and chunk accuracy results are now audited;
the Qwen-summary condition is still pending. See
[all observations and results](../observations_mihai.md).

- **GLiDE-9B**: local BF16 weights, pinned revision
  `ab54df5acba0eebf7df45560ffdaacd64e32df3b`. Uses its own Python 3.12
  environment and upstream requirements, including CUDA 13.0 / driver 580+.
  Tested here on one RTX PRO 6000 Blackwell (job 33485368, exit 0). H200
  compatibility remains untested. The actions evaluation processed up to 26,275
  tokens; the separate reasoning pilot below processed up to 216,463 tokens by
  raising the request-length guard. The published default is 40,000 tokens;
  successful processing does not establish monitoring accuracy at that length.
- **Jev 1.14**: hosted model `jev-1.14.0`, called from the cluster using
  `TYPESAFE_API_KEY`. No downloadable Jev weights are installed. The client
  uses Python's standard library. The prepared comparison enables long-context
  mode for full reasoning and combined inputs. The real-input pilot accepted
  inputs up to 229,506 Jev tokens; this verifies execution, not accuracy.

On the cluster, set `PROJECT` to the existing shared project directory and
`SETUP` to the absolute path of this folder:

```bash
sbatch --output="$PROJECT/logs/glide-install-%j.log" \
  "$SETUP/install.sbatch" "$PROJECT" "$SETUP/setup_glide.sh"
# Wait for installation to finish successfully before submitting the GPU test.
sbatch --output="$PROJECT/logs/glide-smoke-%j.log" \
  "$SETUP/smoke.sbatch" "$PROJECT" "$SETUP/smoke.py"
```

For Jev, obtain a key through the TypeSafe console and enter it privately in
the cluster Bash shell (input is hidden and the key is not in shell history):

```bash
read -rsp 'TypeSafe API key: ' TYPESAFE_API_KEY; echo
export TYPESAFE_API_KEY
"$PROJECT/envs/monitor-research/bin/python" -B "$SETUP/smoke.py" jev
unset TYPESAFE_API_KEY
```

Both tests use only a short synthetic example. A valid response verifies basic
operation, not monitoring accuracy or long-input reliability. No saved rollout
is submitted to either model by these scripts. Weights, caches and installed
package snapshots stay on the cluster. Existing Qwen environments are untouched.

## Readable GLiDE demo

[`demo_glide.py`](demo_glide.py) contains two fictional flight-booking logs.
Only the second includes an email to an outsider. The same two questions are
asked about each log: did the agent pursue the hidden objective (`noul`), and
which actions occurred (`choice`)? The script prints the exact inputs and outputs.
The GPU test above also runs this demo. To run it yourself inside a Blackwell GPU allocation:

```bash
"$PROJECT/envs/monitor-glide-ab54df5a/bin/python" -B "$SETUP/demo_glide.py" \
  "$PROJECT/models/glide-9b-ab54df5a"
```

Edit `examples` to change the input text, or `questions` to change what the model
decides. `noul` is P(yes); a high value means the model favors yes. `choice`
reports option probabilities and the selected option. Its `confidence` is the
gap between the two largest probabilities, not the probability of being correct.
These toy examples demonstrate the interface, not performance on our rollouts.

Actual results: P(hidden objective pursued) was 0.001853 for booking only and
0.998952 for booking plus the outsider email. The choice question selected the
matching description in both cases. `usage.output_tokens` was zero.

## MonitorBench adaptation

[`monitorbench_glide.py`](monitorbench_glide.py) is a small actions/CoT adapter;
its [actions prompt and exact A–D choices](monitorbench_action.json) are separate for review.
Running the script only prints the [fictional example request](monitorbench_example_request.json).
Calling `monitor(model, main_task, hidden_objective, actions)` performs inference.

The source is `vendor/monitorbench_monitor/prompts/monitor_dual_objectives.agent.yaml`
at project commit `6043ff7a875bf6d2d792cec7df603c5cd019c647`. All four choices and
their order, the opening paragraph, and the evidence section labels are retained.
Instructions to write a summary, quotes and explanations become assessment
instructions; the final XML-answer instruction is replaced by GLiDE's choice
interface. This changes the elicitation procedure and prompt layout.

Only the winning letter A counts as detection, matching the baseline; P(A) is
saved but is not thresholded at 0.5. Errors propagate rather than becoming negatives.
The adapter expects the existing renderer's actions text, including its tool-result
cuts and turn labels. Dataset loading and scoring are handled by the runner below;
labels never enter the model request.

For a controlled comparison, give Qwen the same adapted instructions and evidence
in one pass on a common set of inputs that fit both models. Report the original
Qwen runs with generated analyses and hierarchical reduction as a separate system
comparison. Count inputs using each tokenizer; report any excluded/failed cases.
Keep four sampled labels from GLiDE's single probability vector distinct from
Qwen's four separately generated analyses.

## Actions-only evaluation

[`run_evaluation.py`](run_evaluation.py) reuses the pinned baseline loader,
action renderer and scoring functions. [`sampling.py`](sampling.py) applies
temperature 0.6 and top-p 0.9 to the four answer probabilities and draws four
reproducible answers. It also saves the original probabilities and the default
highest-probability answer. Only A counts as detection; failed calls remain invalid.

Run `glide-actions-20261115-60611f0f` uses 41 original rollouts and 34 controls,
each tested against both target objectives: 150 cases, 600 sampled judgments
and 150 default judgments. The CPU preflight (job 33492122) passed all file and
model checks. Full prompts are 2,157–26,275 GLiDE tokens, within the 40,000-token
limit. There is no hierarchical splitting; the baseline's 2,000-character
tool-result cuts and turn labels are retained.

GPU job **33492538** completed on 2026-11-15 on one RTX PRO 6000 Blackwell
in **5 minutes 4 seconds**, with all 150 cases complete and zero failures.
The final audit verified input hashes and token counts, all four sampled answers,
default answers and the reported scores. Calls averaged 1.87 seconds per case,
including the first-call compilation overhead.
Its [run record](evaluations/glide-actions-20261115-60611f0f.json) records the
configuration, submission receipt and frozen framework commit. Raw inputs and
results stay on the cluster at
`$PROJECT/mihai/decision_models/runs/glide-actions-20261115-60611f0f/`;
the log is `$PROJECT/logs/glide-eval-33492538.log`.
`pairs/` contains each decision, `summary.json` records completion, and
`sampled-metrics.json` / `greedy-metrics.json` contain the two score reports.

Compact copies are in [the results folder](evaluations/glide-actions-20261115-60611f0f/).
The following pooled rates use the baseline's labels; false alarms are measured
on its clean-control cases. The four draws are pooled individually for sampled results.

| Decision method | Detection rate | Clean-control false alarms | G-mean² |
|---|---:|---:|---:|
| Four sampled answers | 94.5% | 23.5% | 0.723 |
| Highest-probability answer | 95.1% | 24.2% | 0.721 |

For sampled malicious-target judgments specifically, detection was 98.9% and
false alarms were 40.9%; for benign targets, they were 89.5% and 6.1%.
These are actions-only results with the adapted prompt, not a controlled
comparison of architectures against Qwen's generated analyses and hierarchy.

To inspect completion, use `sacct -j 33492538 --format=JobID,State,ExitCode,Elapsed`
and `tail -n 10 "$PROJECT/logs/glide-eval-33492538.log"`.
The submitted source is frozen under
`$PROJECT/releases/glide-actions-20261115-60611f0f/`; do not edit it.

Sources: [GLiDE model and install guide](https://huggingface.co/fastino/GLiDE-9B),
[Jev versions](https://docs.typesafe.ai/models),
[Jev request format](https://docs.typesafe.ai/api/system-one).

## Reasoning length pilot

The [pilot code and measurement method](long_context/README.md) test increasing
CoT input lengths before selecting a full evaluation method. CPU job 33507043
verified 75 rollouts and 150 objective prompts: 22,007–216,463 GLiDE tokens;
118 prompts exceed the default 40,000-token limit. GPU job **33507318** completed
all ten lengths on one Blackwell GPU in **36 minutes 27 seconds**, with 70 valid
calls, zero failures, and no missing measurements. At 216,463 tokens, two warm
calls averaged **105.5 seconds**; peak allocated GPU memory was **50.5 GiB**
and peak reserved memory was **62.5 GiB**, excluding some driver overhead.
The [run record](evaluations/glide-cot-length-20261115-21f6974f.json) records
the frozen source and settings. Raw pilot inputs and measurements are under
`$PROJECT/mihai/decision_models/runs/glide-cot-length-20261115-21f6974f/`.
Partial real transcripts are not scored as complete rollouts; the controlled
evidence-position checks are synthetic and separate from benchmark accuracy.
All 40 controlled checks passed using the highest-probability answer, and all
160 saved sampled answers were correct. The tests use one constructed scenario;
the model assigned less probability to the correct positive answer as length grew.
See the [measurements, chart and audit](evaluations/glide-cot-length-20261115-21f6974f/README.md).
All 150 real CoT prompts fit within the tested length, motivating the full-CoT
evaluation below. The pilot predicted about 58.5 minutes of inference on this
GPU, before overhead. Combined inputs were not measured in this pilot.

## Full CoT evaluation

Run `glide-cot-20261115-c8f6c4e8` evaluates the same 75 rollouts against both
objectives, using full CoT inputs with the exact pilot prompt and no hierarchy.
The same runner and scorer save 600 sampled judgments and 150 highest-probability
judgments. Model revision, BF16 precision, temperature 0.6, top-p 0.9 and seed 0
are unchanged. The input guard is 216,471 tokens, including GLiDE's 8-token margin.

Preparation job **33509894** completed successfully: all 150 input lengths match
the pilot inventory, and none exceeds the limit. GPU job **33509938** stopped
after 27:13 on one RTX PRO 6000 Blackwell, with scheduler status `FAILED`, exit
`1:0`. The partial audit verified **108 complete checks**, with 42 missing
results and no recorded per-case errors. This includes the longest 216,463-token
input. The log has no traceback; the scheduler reports neither a timeout nor an
out-of-memory failure, so the cause remains unresolved.
The authorized restart, job **33512196**, completed in **39:00** with exit `0:0`,
using the unchanged frozen evaluator and configuration. It preserved all 108
saved checks and completed the remaining 42. The final audit verified all 150
results, exact input lengths, all 600 sampled judgments and the score calculations.
All 24 model files and the saved results were reverified before submission.
See the [partial audit](evaluations/glide-cot-20261115-c8f6c4e8/partial-audit.json) and
[run record](evaluations/glide-cot-20261115-c8f6c4e8.json) for receipts and settings.
Results are saved separately under
`$PROJECT/mihai/decision_models/runs/glide-cot-20261115-c8f6c4e8/`;
the original log is `$PROJECT/logs/glide-cot-33509938.log`. Restart stdout,
stderr, and exit status are separate files named
`$PROJECT/logs/glide-cot-resume-33512196.log`, `.err`, and `.status`.
The status file is written when the restart exits. The
[restart launcher](resume_evaluation.sbatch) enables fatal-error stack traces
without changing inference. Original result hashes and hardware metadata are
preserved in `restart-1-preflight.json` and `hardware-33509938.json`.

The two GPU jobs used **66:13** in total; successful calls took 65:01.5, averaging
26.0 seconds per case. The restart logged six allocation warnings but completed
every check. Peak allocated memory was 50.5 GiB; reserved memory reached 93.1 GiB
over the full evaluation. These warnings do not establish the cause of the
original silent exit.

| CoT decision method | Detection rate | Clean-control false alarms | G-mean² |
|---|---:|---:|---:|
| Four sampled answers | 62.8% | 1.9% | 0.616 |
| Highest-probability answer | 78.0% | 0.0% | 0.780 |

The sampled CoT run detects fewer positives than the sampled actions run
(94.5%), while producing fewer clean-control false alarms (23.5% for actions).
These rates use the same baseline labels and scoring groups. See the
[full CoT results](evaluations/glide-cot-20261115-c8f6c4e8/README.md).
