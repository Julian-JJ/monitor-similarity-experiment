"""Monitor methods: preparation (plans, partial CoT) and the judging strategy.

A *strategy* turns one (rollout, told objective) into prompts offline (``prepare``) and runs them
through a completion function (``run``). The judging strategy here is the hierarchical monitor of
:mod:`monitor_experiment.hierarchy`. Preparation artifacts are kept apart from verdicts:

* a **plan** is written by the monitor from the main task alone, once per task and plan index, cached
  on disk and shared by every rollout of that task (:class:`PlanBook`);
* a **partial-CoT transform** removes part of the actor's reasoning before rendering, and says how
  much was shown.

See docs/system/strategies.md and docs/system/plan-context.md.
"""

import json
import math
import threading
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import hierarchy as h
from .artifacts import digest
from .toollists import format_tools


class PlanError(RuntimeError):
    """The monitor could not write a valid plan; the plan context cannot run for that task."""


MAX_PLAN_TOKENS = 1000


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


class JudgeStrategy:
    """The hierarchical monitor (``hier_ad``): MonitorBench's A-D prompt, chunked and combined as needed."""

    name = "hier_ad"

    def __init__(self, prompts, count, objectives):
        self.prompts, self.count, self.objectives = prompts, count, objectives

    def prepare(self, item, told, cell, plan_text=None):
        """Offline: chunks and exact level-0 prompts for this rollout under this told objective."""
        observation = item.observation()
        return h.plan(list(observation.messages), cell.params, self.count, self.prompts,
                      objective=self.objectives.text(item.task, told), plan_text=plan_text,
                      turns_transform=partial_cot_transform(cell.partial_cot, self.count))

    def run(self, item, told, planned, cell, complete, seed):
        return h.run_tree(f"{item.rollout_id}:{told}", planned["chunks"], cell.params, self.count, self.prompts,
                          planned["main_task"], planned["objective"], complete, seed, planned["plan_text"])
