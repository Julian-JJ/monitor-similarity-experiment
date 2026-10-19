"""The tools each task's agent had, read from the vendored source without importing it.

The monitor's plan is written from the task and a neutral list of the agent's tools (names and one-line
descriptions). The list is taken from the environment definitions, never from a rollout, so it cannot carry
information about what the agent did. ``ast`` parses the source, so none of the environment's heavy
dependencies are needed. See docs/system/plan-context.md.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/monitorbench_agent"
ENVIRONMENT_FILES = {"bank_transfer_2": "banking_environment.py",
                     "american_airlines_2": "travel_environment.py",
                     "spam_filter_update": "spam_filter_update_environment.py"}


def function_docs(tools_dir):
    """``{function name: first line of its docstring}`` for every top-level function under ``tools/``."""
    docs = {}
    for path in sorted(Path(tools_dir).glob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.FunctionDef):
                text = ast.get_docstring(node) or ""
                docs[node.name] = text.strip().splitlines()[0].strip() if text.strip() else ""
    return docs


def tool_names(environment_file):
    """Names passed to ``self.add_tools([...])``, in order, plus ``end_task`` (added by the base class)."""
    tree = ast.parse(Path(environment_file).read_text())
    names = ["end_task"]
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_tools"
                and node.args and isinstance(node.args[0], ast.List)):
            names += [element.id for element in node.args[0].elts if isinstance(element, ast.Name)]
    return names


def tool_lists(vendor=VENDOR):
    docs = function_docs(Path(vendor) / "tools")
    lists = {}
    for task, filename in ENVIRONMENT_FILES.items():
        names = tool_names(Path(vendor) / "environments" / filename)
        missing = [n for n in names if n not in docs]
        if missing:
            raise ValueError(f"{task}: tools without a definition under tools/: {missing}")
        lists[task] = [{"name": n, "description": docs[n]} for n in dict.fromkeys(names)]
    return lists


def format_tools(entries):
    """The text placed in the plan prompt: one ``- name: description`` line per tool."""
    return "\n".join(f"- {e['name']}: {e['description']}" if e["description"] else f"- {e['name']}" for e in entries)
