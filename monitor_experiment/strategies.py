"""Monitor methods: preparation (plans, executions, plan comparisons, partial CoT) and the judging strategy.

A *strategy* turns one (rollout, told objective) into prompts offline (``prepare``) and runs them
through a completion function (``run``). The judging strategy here is the hierarchical monitor of
:mod:`monitor_experiment.hierarchy`. Preparation artifacts are kept apart from verdicts:

* a **plan** is written by the monitor from the main task alone, once per task and plan index, cached
  on disk and shared by every rollout of that task (:class:`PlanBook`);
* an **execution** has the monitor attempt the main task in a fresh simulated environment and summarize
  its attempt into a reference block, once per task and index (:class:`ExecutionBook`);
* a **plan comparison** compares a rollout's transcript against the monitor's reference plan without
  seeing the hidden objective, cached once per rollout (:class:`ComparisonBook`);
* a **partial-CoT transform** removes part of the actor's reasoning before rendering, and says how
  much was shown.

See docs/system/strategies.md and docs/system/plan-context.md.
"""

import json
import math
import re
import threading
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import hierarchy as h
from .artifacts import digest
from .toollists import format_tools


class PlanError(RuntimeError):
    """The monitor could not produce a valid preparation artifact (plan, execution summary, or comparison)."""


MAX_PLAN_TOKENS = 1000
TOOL_CALL_TAG = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
SECTION_KEYS = {
    "none": "plan_section",
    "plan": "plan_section",
    "execute": "execute_section",
    "plan_compare": "plan_compare_section",
}


def partial_cot_transform(config, count):
    """A ``turns_transform`` for :func:`hierarchy.plan`, or ``None`` when ``config`` is empty.

    ``{"mode": "turns", "value": p}`` keeps the reasoning of the first ceil(p * turns) turns.
    ``{"mode": "tokens", "value": p}`` keeps the first p of all reasoning tokens, cutting the turn that
    straddles the limit at a paragraph, line or word boundary. Actions, tool results and visible text are
    never touched. The transform reports how much reasoning was shown; it is a deliberate, recorded cut.
    """
    if not config:
        return None
    mode, value = config["mode"], config["value"]

    def transform(turns):
        sizes = [count(t["reasoning"]) if t["reasoning"].strip() else 0 for t in turns]
        total, shown, out = sum(sizes), 0, []
        if mode == "turns":
            keep = math.ceil(value * len(turns))
            for index, turn in enumerate(turns):
                if index < keep:
                    out.append(turn)
                    shown += sizes[index]
                else:
                    out.append({**turn, "reasoning": ""})
        else:
            remaining = value * total
            for index, turn in enumerate(turns):
                if sizes[index] <= remaining:
                    out.append(turn)
                    shown += sizes[index]
                    remaining -= sizes[index]
                elif remaining >= 1:
                    first = h.split_text(turn["reasoning"], int(remaining), count)[0]
                    out.append({**turn, "reasoning": first})
                    shown += count(first)
                    remaining = 0
                else:
                    out.append({**turn, "reasoning": ""})
        stats = {"mode": mode, "value": value, "turns_total": len(turns),
                 "turns_with_reasoning_shown": sum(1 for t in out if t["reasoning"].strip()),
                 "reasoning_tokens_total": total, "reasoning_tokens_shown": shown,
                 "fraction_shown": (shown / total) if total else 0.0}
        return out, stats
    return transform


class PlanBook:
    """Plans written by one monitor, cached in a JSONL file keyed by a content hash.

    The key covers the monitor, the task text, the tool list, the plan prompt and the plan index, so a
    cached plan is only ever reused when everything that shaped it is unchanged.
    """

    def __init__(self, path, prompts, tool_lists, count, monitor_identity, k, seed=0, max_attempts=2):
        self.path, self.prompts, self.tool_lists, self.count = Path(path), prompts, tool_lists, count
        self.monitor_identity, self.k, self.seed, self.max_attempts = monitor_identity, k, seed, max_attempts
        self.lock = threading.Lock()
        self.plans = {}
        if self.path.is_file():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.plans[record["plan_id"]] = record

    def plan_id(self, task, main_task, index):
        return digest({"monitor": self.monitor_identity, "task": task, "index": index,
                       "main_task": digest(main_task), "tools": digest(self.tool_lists[task]),
                       "prompt": digest(self.prompts["plan"]), "seed": self.seed})

    def index_for(self, sample):
        """Which of the k plans a rollout uses: its sample number modulo k (docs/plan/07 2.4)."""
        return sample % self.k

    def get(self, task, main_task, sample):
        try:
            return self.plans[self.plan_id(task, main_task, self.index_for(sample))]
        except KeyError:
            raise PlanError(f"No plan for task {task!r}, index {self.index_for(sample)}; call ensure() first") from None

    def ensure(self, main_tasks, complete):
        """Write every missing plan. ``main_tasks`` maps task name to its main-task text."""
        made = []
        for task in sorted(main_tasks):
            for index in range(self.k):
                pid = self.plan_id(task, main_tasks[task], index)
                if pid not in self.plans:
                    made.append(self._write(pid, task, main_tasks[task], index, complete))
        return made

    def _write(self, pid, task, main_task, index, complete):
        prompt = self.prompts["plan"].format(input=main_task, tools=format_tools(self.tool_lists[task]))
        base = self.seed * 10 ** 9 + 9 * 10 ** 8 + (zlib.crc32(task.encode()) % 10 ** 4) * 1000 + index * 10
        attempts = []
        for number in range(self.max_attempts):
            output = complete(prompt, base + number)
            text = (output.get("text") or "").strip()
            reason = None
            if output.get("finish_reason") != "stop":
                reason = f"finish_reason={output.get('finish_reason')!r}"
            elif not text:
                reason = "empty plan"
            elif self.count(text) > MAX_PLAN_TOKENS:
                reason = f"plan has {self.count(text)} tokens; the limit is {MAX_PLAN_TOKENS}"
            attempts.append({"seed": base + number, "valid": reason is None, "reason": reason,
                             "finish_reason": output.get("finish_reason"), "usage": output.get("usage"),
                             "latency_seconds": output.get("latency_seconds")})
            if reason is None:
                record = {"plan_id": pid, "task": task, "index": index, "text": text, "tokens": self.count(text),
                          "prompt_sha256": digest(prompt), "attempts": attempts,
                          "created_at": datetime.now(timezone.utc).isoformat()}
                with self.lock:
                    self.plans[pid] = record
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a") as stream:
                        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                return record
        raise PlanError(f"Task {task!r}, plan {index}: no valid plan in {self.max_attempts} attempts: "
                        + "; ".join(a["reason"] for a in attempts))


class _SyntheticEnvironment:
    """Fallback simulated environment for synthetic test tasks not in :data:`environments.TASKS`."""

    def __init__(self, tools):
        self._names = {t["name"] for t in tools} | {"end_task"}
        self.called = []

    def execute(self, name, arguments):
        if name not in self._names:
            return None, f"ToolNotFoundError: unknown tool {name!r}"
        self.called.append((name, arguments))
        return f"executed {name}({ json.dumps(arguments, sort_keys=True) })", None

    def evaluate(self):
        return {"type": "programmatic", "main": {"score": 1.0 if self.called else 0.0, "success": bool(self.called)},
                "side": {"malicious": False, "benign": False}, "side_success": None, "target_variant": "main_only"}


def parse_tool_calls(output):
    """Extract ``[{"name": str, "arguments": dict, "error": str|None}]`` from ``complete`` output."""
    calls = []
    for raw in (output.get("tool_calls") or []):
        fn = raw.get("function") or {}
        name = fn.get("name") or raw.get("name")
        args = fn.get("arguments", raw.get("arguments", {}))
        try:
            parsed = json.loads(args) if isinstance(args, str) else args
            if not isinstance(parsed, dict):
                raise ValueError("arguments must be a JSON object")
            calls.append({"name": str(name), "arguments": parsed, "error": None})
        except (ValueError, TypeError) as error:
            calls.append({"name": str(name or ""), "arguments": {}, "error": f"Invalid tool arguments: {error}"})
    text = output.get("text") or ""
    for match in TOOL_CALL_TAG.finditer(text):
        try:
            payload = json.loads(match.group(1))
            if not isinstance(payload, dict) or not isinstance(payload.get("name"), str) or not payload["name"]:
                raise ValueError("expected an object with a non-empty string 'name'")
            arguments = payload.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(arguments, dict):
                raise ValueError("'arguments' must be a JSON object")
            calls.append({"name": payload["name"], "arguments": arguments, "error": None})
        except (ValueError, TypeError) as error:
            calls.append({"name": "", "arguments": {}, "error": f"Invalid tool_call JSON: {error}"})
    return calls


def _render_execution_steps(steps, truncate_chars=2000):
    if not steps:
        return "No steps taken yet."
    lines = []
    for step in steps:
        lines.append(f"=== Step {step['turn']} ===")
        if step.get("assistant_text"):
            lines.append(step["assistant_text"])
        for call in step["calls"]:
            args = json.dumps(call["arguments"], ensure_ascii=False, sort_keys=True)
            out = call["error"] if call["error"] else str(call["result"] if call["result"] is not None else "")
            if truncate_chars is not None and len(out) > truncate_chars:
                out = out[:truncate_chars] + "...[truncated]"
            lines.append(f"{call['name']}({args}) -> {out}")
    return "\n".join(lines)


class ExecutionBook:
    """Task attempts executed by one monitor in a fresh ``main_only`` simulated environment, then summarized.

    Cached in ``runs/<name>/executions/<monitor>.jsonl`` keyed by a content hash. Like :class:`PlanBook`,
    ``k`` independent executions are run per task and assigned to rollouts via ``sample % k``.
    """

    def __init__(self, path, prompts, tool_lists, count, monitor_identity, k, seed=0, max_attempts=2,
                 max_turns=20, truncate_chars=2000, environment_factory=None):
        self.path, self.prompts, self.tool_lists, self.count = Path(path), prompts, tool_lists, count
        self.monitor_identity, self.k, self.seed, self.max_attempts = monitor_identity, k, seed, max_attempts
        self.max_turns, self.truncate_chars = max_turns, truncate_chars
        self.environment_factory = environment_factory
        self.lock = threading.Lock()
        self.executions = {}
        if self.path.is_file():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.executions[record["execution_id"]] = record

    def execution_id(self, task, main_task, index):
        return digest({"monitor": self.monitor_identity, "task": task, "index": index,
                       "main_task": digest(main_task), "tools": digest(self.tool_lists[task]),
                       "agent_prompt": digest(self.prompts["execute_agent"]),
                       "summary_prompt": digest(self.prompts["execute_summary"]),
                       "max_turns": self.max_turns, "seed": self.seed})

    def index_for(self, sample):
        return sample % self.k

    def get(self, task, main_task, sample):
        try:
            return self.executions[self.execution_id(task, main_task, self.index_for(sample))]
        except KeyError:
            raise PlanError(f"No execution for task {task!r}, index {self.index_for(sample)}; call ensure() first") from None

    def _make_environment(self, task, seed):
        if self.environment_factory is not None:
            return self.environment_factory(task, "main_only", seed)
        if task in ("bank_transfer_2", "american_airlines_2", "spam_filter_update"):
            from . import environments as env_mod
            return env_mod.Environment(task, "main_only", seed)
        return _SyntheticEnvironment(self.tool_lists[task])

    def ensure(self, main_tasks, complete):
        """Run and summarize every missing task execution."""
        made = []
        for task in sorted(main_tasks):
            for index in range(self.k):
                eid = self.execution_id(task, main_tasks[task], index)
                if eid not in self.executions:
                    made.append(self._write(eid, task, main_tasks[task], index, complete))
        return made

    def _write(self, eid, task, main_task, index, complete):
        tools_text = format_tools(self.tool_lists[task])
        base = self.seed * 10 ** 9 + 8 * 10 ** 8 + (zlib.crc32(task.encode()) % 10 ** 4) * 1000 + index * 100
        env = self._make_environment(task, base)
        steps, turn_attempts, tool_calls_made = [], [], []
        termination = "max_turns"
        for turn in range(1, self.max_turns + 1):
            history_text = _render_execution_steps(steps, self.truncate_chars)
            prompt = self.prompts["execute_agent"].format(input=main_task, tools=tools_text, history=history_text)
            output = complete(prompt, base + turn)
            turn_attempts.append({"turn": turn, "seed": base + turn, "finish_reason": output.get("finish_reason"),
                                  "usage": output.get("usage"), "latency_seconds": output.get("latency_seconds")})
            if output.get("finish_reason") != "stop":
                termination = "incomplete"
                break
            calls = parse_tool_calls(output)
            visible = TOOL_CALL_TAG.sub("", output.get("text") or "").strip()
            if not calls:
                steps.append({"turn": turn, "assistant_text": visible, "calls": []})
                termination = "final_answer"
                break
            step_calls, ended = [], False
            for call in calls:
                if call["error"]:
                    step_calls.append({"name": call["name"] or "invalid", "arguments": call["arguments"],
                                       "result": None, "error": call["error"]})
                    continue
                if call["name"] == "end_task":
                    step_calls.append({"name": "end_task", "arguments": call["arguments"],
                                       "result": "Task ended.", "error": None})
                    tool_calls_made.append("end_task")
                    ended = True
                    break
                try:
                    result, error = env.execute(call["name"], call["arguments"])
                except Exception as exc:
                    result, error = None, f"{type(exc).__name__}: {exc}"
                step_calls.append({"name": call["name"], "arguments": call["arguments"], "result": result, "error": error})
                tool_calls_made.append(call["name"])
            steps.append({"turn": turn, "assistant_text": visible, "calls": step_calls})
            if ended:
                termination = "end_task"
                break
        evaluation = env.evaluate()
        main_eval = (evaluation or {}).get("main") or {}
        main_success = bool(main_eval.get("success", False))
        main_score = main_eval.get("score")
        attempt_summary = (_render_execution_steps(steps, self.truncate_chars)
                           + f"\n\nTermination: {termination} | Main task success: {main_success}")
        summary_prompt = self.prompts["execute_summary"].format(input=main_task, tools=tools_text, attempt=attempt_summary)
        summary_base = base + self.max_turns + 50
        attempts = []
        for number in range(self.max_attempts):
            output = complete(summary_prompt, summary_base + number)
            text = (output.get("text") or "").strip()
            reason = None
            if output.get("finish_reason") != "stop":
                reason = f"finish_reason={output.get('finish_reason')!r}"
            elif not text:
                reason = "empty execution summary"
            elif self.count(text) > MAX_PLAN_TOKENS:
                reason = f"execution summary has {self.count(text)} tokens; the limit is {MAX_PLAN_TOKENS}"
            attempts.append({"seed": summary_base + number, "valid": reason is None, "reason": reason,
                             "finish_reason": output.get("finish_reason"), "usage": output.get("usage"),
                             "latency_seconds": output.get("latency_seconds")})
            if reason is None:
                record = {"execution_id": eid, "task": task, "index": index, "text": text, "tokens": self.count(text),
                          "turns": len(steps), "termination": termination, "tool_calls": tool_calls_made,
                          "main_success": main_success, "main_score": main_score,
                          "prompt_sha256": digest(summary_prompt), "turn_attempts": turn_attempts,
                          "attempts": attempts, "created_at": datetime.now(timezone.utc).isoformat()}
                with self.lock:
                    self.executions[eid] = record
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a") as stream:
                        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                return record
        raise PlanError(f"Task {task!r}, execution {index}: no valid execution summary in {self.max_attempts} attempts: "
                        + "; ".join(a["reason"] for a in attempts))


def format_plan_comparison(plan_text, comparison_text):
    """Combine a reference plan and its per-rollout divergence comparison into the block placed in judging prompts."""
    return f"Reference plan:\n{plan_text.strip()}\n\nComparison with the agent's work:\n{comparison_text.strip()}"


class ComparisonBook:
    """Per-rollout comparisons of the actor's transcript against the monitor's reference plan.

    Written without seeing any hidden objective, so one comparison per (rollout, plan, scope/transform) is
    shared across both told objectives. Cached in ``runs/<name>/comparisons/<monitor>.jsonl``.
    """

    def __init__(self, path, prompts, count, monitor_identity, seed=0, max_attempts=2):
        self.path, self.prompts, self.count = Path(path), prompts, count
        self.monitor_identity, self.seed, self.max_attempts = monitor_identity, seed, max_attempts
        self.lock = threading.Lock()
        self.comparisons = {}
        if self.path.is_file():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    record = json.loads(line)
                    self.comparisons[record["comparison_id"]] = record

    def comparison_id(self, rollout_id, plan_id, cell):
        return digest({"monitor": self.monitor_identity, "rollout_id": rollout_id, "plan_id": plan_id,
                       "scope": cell.params["scope"], "partial_cot": cell.partial_cot,
                       "truncate_chars": cell.params["truncate_chars"], "labels": cell.params["labels"],
                       "prompt": digest(self.prompts["plan_compare"]), "seed": self.seed})

    def ensure_one(self, item, plan_record, cell, complete):
        cid = self.comparison_id(item.rollout_id, plan_record["plan_id"], cell)
        with self.lock:
            if cid in self.comparisons:
                return self.comparisons[cid]
        observation = item.observation()
        rollout_turns = h.turns(list(observation.messages))
        transform = partial_cot_transform(cell.partial_cot, self.count)
        if transform is not None:
            rollout_turns, _ = transform(rollout_turns)
        parts, _ = h.segments(rollout_turns, {**cell.params, "chunk_tokens": 10 ** 9}, self.count)
        transcript_text = "\n\n".join(p["text"] for p in parts)
        probe = self.prompts["plan_compare"].format(input=observation.main_task, plan=plan_record["text"], transcript="")
        room = max(64, h.input_limit(cell.params) - self.count(probe) - 16)
        if self.count(transcript_text) > room:
            transcript_text = h.split_text(transcript_text, room, self.count)[0]
        prompt = self.prompts["plan_compare"].format(
            input=observation.main_task, plan=plan_record["text"], transcript=transcript_text)
        base = (self.seed * 10 ** 9 + 7 * 10 ** 8
                + (zlib.crc32(f"{item.item_id}|{plan_record['plan_id']}|{cell.params['scope']}".encode()) % 10 ** 5) * 10)
        attempts = []
        for number in range(self.max_attempts):
            output = complete(prompt, base + number)
            text = (output.get("text") or "").strip()
            reason = None
            if output.get("finish_reason") != "stop":
                reason = f"finish_reason={output.get('finish_reason')!r}"
            elif not text:
                reason = "empty comparison"
            elif self.count(text) > MAX_PLAN_TOKENS:
                reason = f"comparison has {self.count(text)} tokens; the limit is {MAX_PLAN_TOKENS}"
            attempts.append({"seed": base + number, "valid": reason is None, "reason": reason,
                             "finish_reason": output.get("finish_reason"), "usage": output.get("usage"),
                             "latency_seconds": output.get("latency_seconds")})
            if reason is None:
                record = {"comparison_id": cid, "item_id": item.item_id, "rollout_id": item.rollout_id,
                          "plan_id": plan_record["plan_id"], "scope": cell.params["scope"],
                          "text": text, "tokens": self.count(text), "prompt_sha256": digest(prompt),
                          "attempts": attempts, "created_at": datetime.now(timezone.utc).isoformat()}
                with self.lock:
                    if cid not in self.comparisons:
                        self.comparisons[cid] = record
                        self.path.parent.mkdir(parents=True, exist_ok=True)
                        with self.path.open("a") as stream:
                            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                    return self.comparisons[cid]
        raise PlanError(f"Rollout {item.item_id!r}, plan {plan_record['plan_id'][:12]}: no valid comparison in "
                        f"{self.max_attempts} attempts: " + "; ".join(a["reason"] for a in attempts))


class JudgeStrategy:
    """The hierarchical monitor (``hier_ad``): MonitorBench's A-D prompt, chunked and combined as needed."""

    name = "hier_ad"

    def __init__(self, prompts, count, objectives):
        self.prompts, self.count, self.objectives = prompts, count, objectives

    def prepare(self, item, told, cell, plan_text=None):
        """Offline: chunks and exact level-0 prompts for this rollout under this told objective."""
        observation = item.observation()
        section_key = SECTION_KEYS.get(cell.label.get("task_context", "none"), "plan_section")
        return h.plan(list(observation.messages), cell.params, self.count, self.prompts,
                      objective=self.objectives.text(item.task, told), plan_text=plan_text,
                      turns_transform=partial_cot_transform(cell.partial_cot, self.count),
                      section_key=section_key)

    def run(self, item, told, planned, cell, complete, seed):
        section_key = planned.get("section_key") or SECTION_KEYS.get(cell.label.get("task_context", "none"), "plan_section")
        return h.run_tree(f"{item.rollout_id}:{told}", planned["chunks"], cell.params, self.count, self.prompts,
                          planned["main_task"], planned["objective"], complete, seed, planned["plan_text"],
                          section_key=section_key)
