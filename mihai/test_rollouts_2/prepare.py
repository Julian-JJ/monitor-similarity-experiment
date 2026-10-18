#!/usr/bin/env python3
"""Freeze a small, deterministic MonitorBench screening set before inference."""
import ast
import contextlib
import csv
import hashlib
import io
import json
import string
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / "upstream"
REVISION = "b6229e4b8ea9abcec38d61159c9cbd0f577ddf35"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upstream_records(module, class_name, dataset, task, conditions):
    # Execute only the inspected, pinned data-loading method. Do not import the
    # upstream pipeline, whose module-level code downloads resources and models.
    tree = ast.parse((UPSTREAM / module).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "load_dataset")
    namespace = {"json": json, "string": string}
    exec(compile(ast.Module(body=[method], type_ignores=[]), module, "exec"), namespace)
    records = []
    obj = SimpleNamespace(
        args=SimpleNamespace(device="0", stress_test=",".join(conditions)),
        vllm_cfg={"evaluated_llm": {"tensor_parallel": 1}},
        dataset_path=UPSTREAM / dataset, task=task,
        save_shard_records=lambda path, rows, shards: records.extend(rows))
    with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
        namespace["load_dataset"](obj, Path(folder))
    return records


def build():
    manifest = json.loads((UPSTREAM / "manifest.json").read_text())
    assert manifest["revision"] == REVISION
    for name, info in manifest["files"].items():
        assert sha(UPSTREAM / name) == info["sha256"], name
    definitions = [
        ("knowledge", "cue_condition", "pipeline/intervention.py", "ConditionKnowledge",
         "datasets/cue_condition/knowledge/knowledge.json", "cue.condition.knowledge", ["standard", "original"]),
        ("preference", "cue_condition", "pipeline/intervention.py", "ConditionPreference",
         "datasets/cue_condition/preference/Preference.json", "cue.condition.preference", ["standard"]),
        ("logic", "cue_answer", "pipeline/intervention.py", "AnswerLogic",
         "datasets/cue_answer/brute_logic/brute_logic.json", "cue.answer.logic", ["standard", "original"]),
        ("steganography", "dual_objectives", "pipeline/outcome.py", "DualSteganography",
         "datasets/dual_objective/databricks_dolly/task_writing_steganography.json", "dual_objectives.steganography", ["standard"]),
        ("summarization", "dual_objectives", "pipeline/outcome.py", "DualSummarization",
         "datasets/dual_objective/summary/task_writing_summarization.json", "dual_objectives.summarization", ["standard"]),
    ]
    cases = []
    for family, category, module, cls, path, task, conditions in definitions:
        source = json.loads((UPSTREAM / path).read_text())
        generated = upstream_records(module, cls, path, task, conditions)
        for i, item in enumerate(source[:2]):
            rows = [r for r in generated if int(r["task_id"].split("_")[0]) == i]
            for row in rows:
                mode = row["metadata"]["stress_test"]
                cases.append({"case_id": f"{family}-{i:02d}-{mode}", "family": family,
                    "category": category, "condition": mode, "source_path": path,
                    "source_sha256": sha(UPSTREAM / path), "source_index": i,
                    "source_id": item.get("id", item.get("example_id")),
                    "messages": row["messages"], "target": row["target"],
                    "prompt_basis": "exact pinned upstream load_dataset method",
                    "main_grade_method": "manual_visible_answer_review" if family in ("logic", "steganography", "summarization", "knowledge") else "boxed_choice",
                    "side_target": row["target"] if category == "dual_objectives" else None})
            if category == "dual_objectives":
                question = item["Input"] if family == "steganography" else (
                    item["Instruction"] + "\nSTART OF THE REPORT: \n" + item["Input"] + "\nEND OF THE REPORT")
                control = dict(cases[-1])
                control.update(case_id=f"{family}-{i:02d}-main_only", condition="main_only",
                               messages=[{"role": "user", "content": question}],
                               prompt_basis="adapted control: same upstream main prompt, side objective omitted", side_target=None)
                cases.append(control)
    path = "datasets/necessary_steps/lore/lore.csv"
    rows = list(csv.DictReader((UPSTREAM / path).open(encoding="utf-8-sig")))
    chosen = [(i, r) for i, r in enumerate(rows)
              if r["domain"] == "math" and r["shortcut_affect_brute_force_evaluation"] == "NO"][:2]
    assert [r["gt_final"] for _, r in chosen] == ["24", "10"]
    for i, row in chosen:
        cases.append({"case_id": f"multistep_math-{i:02d}-standard", "family": "multistep_math",
            "category": "necessary_steps", "condition": "standard", "source_path": path,
            "source_sha256": sha(UPSTREAM / path), "source_index": i, "source_id": row["problem_id"],
            "messages": [{"role": "user", "content": row["prompt"]}], "target": row["gt_final"],
            "side_target": None, "prompt_basis": "exact pinned CSV prompt; upstream eligibility filter",
            "main_grade_method": "final_integer"})
    assert len(cases) == 20 and len({c["case_id"] for c in cases}) == 20
    return {"experiment": "test_rollouts_2", "upstream_revision": REVISION,
        "selection_rule": "First two published rows per task type; first two eligible mathematics rows for necessary steps. Selected before inference, never replaced based on outcome.",
        "distinct_problems": 12, "standard_cases": 12, "control_cases": 8,
        "cases": cases}


if __name__ == "__main__":
    destination = ROOT / "selection.json"
    content = json.dumps(build(), ensure_ascii=False, indent=2) + "\n"
    if destination.exists():
        assert destination.read_text() == content, "Refusing to change an existing selection"
    else:
        destination.write_text(content)
    print(f"Frozen 12 problems / 20 requests; selection SHA256={sha(destination)}")
