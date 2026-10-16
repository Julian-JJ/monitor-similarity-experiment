"""Adapter to the pinned simulated MonitorBench environments.

Upstream uses top-level package names; load one vendored source tree per process.
Do not import a second MonitorBench/agent framework into this interpreter.
"""

import asyncio
import importlib
import random
import sys
from pathlib import Path

from .artifacts import digest, read_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor" / "monitorbench_agent"
TASKS = ("bank_transfer_2", "american_airlines_2", "spam_filter_update")


def provenance():
    manifest = read_json(SOURCE / "manifest.json")
    # Hash the actual files, so local evaluator/tool edits cannot reuse old labels.
    import hashlib
    actual = {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
              for name in manifest["files"]}
    return {"repository": manifest["repository"], "revision": manifest["revision"],
            "source_hash": digest(actual), "modified": actual != manifest["files"]}


def initialize_imports():
    for name in ("utils", "tools", "environments", "environment_classes", "task_pairs", "task_evaluation"):
        existing = sys.modules.get(name)
        if existing and not all(str(SOURCE) in str(p) for p in getattr(existing, "__path__", [])):
            raise RuntimeError(f"Conflicting top-level module: {name}; use a fresh process")
    if str(SOURCE) not in sys.path:
        sys.path.insert(0, str(SOURCE))
    from utils.path_utils import set_project_root
    set_project_root(SOURCE)


class Environment:
    def __init__(self, task, variant, seed):
        if task not in TASKS or variant not in ("benign", "malicious", "main_only"):
            raise ValueError("Unsupported task or objective variant")
        initialize_imports()
        random.seed(seed)
        from utils.functions_runtime import FunctionsRuntime
        self.task = task
        self.variant = variant
        self.definition = importlib.import_module(f"task_pairs.{task}.task_definition").TaskDefinition()
        self.state = self.definition.environment
        self.evaluator = importlib.import_module(f"task_evaluation.{task}_evaluation").TaskEvaluation(self.definition)
        self.runtime = FunctionsRuntime()
        for tool in self.state.available_tools:
            self.runtime.register_function(tool)

    def prompts(self):
        return [
            {"role": "system", "content": self.definition.construct_system_message(
                give_hint=False, thinking_time="baseline",
                variant="malicious" if self.variant == "main_only" else self.variant,
                include_secondary_task=self.variant != "main_only")},
            {"role": "user", "content": self.definition.user_query},
        ]

    def tools(self):
        return [{"type": "function", "function": {
            "name": function.name, "description": function.full_docstring,
            "parameters": function.parameters.model_json_schema()}}
            for function in self.runtime.functions.values()]

    def execute(self, name, arguments):
        result, error = self.runtime.run_function(self.state, name, arguments)
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")
        return result, error

    def snapshot(self):
        return self.state.model_dump(mode="json")

    def restore(self, snapshot):
        self.state = type(self.state).model_validate(snapshot)
        # Upstream initialization validators refill empty inbox/drive/calendar
        # containers. Empty in a checkpoint means deliberately emptied, not new.
        def repair(value, raw):
            if hasattr(type(value), "model_fields"):
                for name in type(value).model_fields:
                    if name not in raw:
                        continue
                    saved = raw[name]
                    if isinstance(saved, (dict, list)) and not saved:
                        setattr(value, name, type(saved)())
                    else:
                        repair(getattr(value, name), saved)
            elif isinstance(value, dict) and isinstance(raw, dict):
                for key, item in value.items():
                    if str(key) in raw:
                        repair(item, raw[str(key)])
            elif isinstance(value, list) and isinstance(raw, list):
                for item, saved in zip(value, raw):
                    repair(item, saved)
        repair(self.state, snapshot)
        if digest(self.snapshot()) != digest(snapshot):
            raise ValueError("Environment snapshot did not round-trip exactly; refusing an unsafe resume")

    def evaluate(self):
        # Each evaluator gets its own copy: grading cannot alter cached final state.
        async def grade():
            main = await self.evaluator.evaluate_main_task([], self.state.model_copy(deep=True))
            labels = {}
            for variant in ("benign", "malicious"):
                labels[variant] = bool(await self.evaluator.evaluate_side_task(
                    self.state.model_copy(deep=True), secondary_task_variant=variant))
            return main, labels
        main, side = asyncio.run(grade())
        if self.task == "bank_transfer_2":
            score = self.evaluator.extract_outcome_scores(main)
        elif self.task == "american_airlines_2":
            flight, reservation = self.evaluator.extract_task_scores(main)
            score = min(flight, float(reservation)) if flight is not None and reservation is not None else None
        else:
            score = float(main)
        if score is None:
            raise ValueError(f"Could not parse main-task evaluator result: {main!r}")
        threshold = self.evaluator.main_task_success_threshold
        # Use the documented raw-score threshold. See vendor/README.md for the
        # upstream spam add_score_columns inconsistency deliberately not reused.
        return {"type": "programmatic", "main": {"raw": main, "score": score,
                "threshold": threshold, "success": score >= threshold},
                "side": side, "side_success": side.get(self.variant),
                "target_variant": self.variant}
