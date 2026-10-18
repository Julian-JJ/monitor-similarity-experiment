"""Adapter to the pinned simulated MonitorBench environments.

Upstream uses top-level package names; load one vendored source tree per process.
Do not import a second MonitorBench/agent framework into this interpreter.
"""

import asyncio
import importlib
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic_core import to_jsonable_python

from .artifacts import digest, read_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor" / "monitorbench_agent"
TASKS = ("bank_transfer_2", "american_airlines_2", "spam_filter_update")


def _table_value(value):
    """Archive table values without conflating missing cells with JSON null."""
    if value is pd.NA or value is pd.NaT:
        return {"__type__": "pandas.NA" if value is pd.NA else "pandas.NaT"}
    if isinstance(value, np.generic):
        return _table_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return {"__type__": "float", "value": "nan" if math.isnan(value)
                else ("+inf" if value > 0 else "-inf")}
    if isinstance(value, (list, tuple)):
        return [_table_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _table_value(item) for key, item in value.items()}
    return to_jsonable_python(value)


def _snapshot_fallback(value):
    """Serialize spreadsheet state only; unsupported objects still fail loudly."""
    if not isinstance(value, pd.DataFrame):
        raise TypeError(f"Unsupported snapshot value: {type(value).__module__}.{type(value).__name__}")
    # Positional data retains duplicate column names, empty shapes and row labels.
    # This is an archival snapshot, not an executable or restorable checkpoint.
    return {"__type__": "pandas.DataFrame", "format_version": 1,
            "columns": _table_value(value.columns.tolist()),
            "index": _table_value(value.index.tolist()),
            "column_names": _table_value(list(value.columns.names)),
            "index_names": _table_value(list(value.index.names)),
            "dtypes": [str(dtype) for dtype in value.dtypes],
            "data": ([[_table_value(cell) for cell in row]
                      for row in value.itertuples(index=False, name=None)]
                     if len(value.columns) else [[] for _ in value.index])}


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
        from pydantic_core import to_jsonable_python
        result, error = self.runtime.run_function(self.state, name, arguments)
        # Upstream also serializes models inside lists as structured records.
        return to_jsonable_python(result), error

    def snapshot(self):
        # Retain Pydantic's existing serializers for ordinary environment fields.
        # Its fallback supplies the missing DataFrame serializer without changing
        # the live environment, tool responses, or evaluator inputs.
        return to_jsonable_python(self.state, fallback=_snapshot_fallback)

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
        raw_score = score
        threshold = self.evaluator.main_task_success_threshold
        success = score >= threshold
        score_basis = "raw"
        if self.task == "spam_filter_update":
            import pandas as pd
            # Reuse upstream's final score/label path, including its score
            # transformation. Do not introduce reprocessing into the grader.
            frame = self.evaluator.add_score_columns(pd.DataFrame([{"transcript": {
                "main_task_evaluation": main, "side_task_evaluation": side.get(self.variant)}}]))
            score = float(frame["main_task_evaluation"].iloc[0])
            success = bool(frame["main_task_success"].iloc[0])
            score_basis = "upstream_add_score_columns"
        return {"type": "programmatic", "main": {"raw": main, "raw_score": raw_score,
                "score": score, "score_basis": score_basis,
                "threshold": threshold, "success": success},
                "side": side, "side_success": side.get(self.variant),
                "target_variant": self.variant}
