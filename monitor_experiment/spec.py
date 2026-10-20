"""Experiment specifications: one TOML file names a monitor, rollout sets and the variations.

``load_spec`` parses and validates a file (unknown keys are errors); ``expand`` turns it
into *cells*, the cross product of the variation axes, each with a deterministic ID. The
ID covers everything that can change a result (monitor identity, settings, prompt files,
tokenizer), so cached results are never reused under different settings. Which values of
each axis exist, and which are not implemented yet, is the table :data:`AXES`.
See docs/system/experiment-spec.md.
"""

import itertools
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import hierarchy as h
from .artifacts import digest


class SpecError(ValueError):
    """The experiment file is malformed or asks for something that is not available."""


HIERARCHY_PRESETS = {
    "upstream-limits": {"context_tokens": 32768, "output_reserve": 16768, "chunk_tokens": 12000},
    "long-context": {"context_tokens": 131072, "output_reserve": 16768, "chunk_tokens": 100000},
}
# axis -> (values accepted now, default, values named in the plan but not implemented)
AXES = {
    "scope": (h.SCOPES, None, ()),
    "task_context": (("none", "plan"), "none", ("execute", "plan_compare")),
    "hierarchy": (tuple(HIERARCHY_PRESETS), "upstream-limits", ()),
    "partial_cot": ("off", "off", ()),  # also "turns:<p>" and "tokens:<p>", 0 < p <= 1
    "followup_visibility": (("none",), "none", ("answer", "cot", "all")),
    "prompt": (("upstream_ad",), "upstream_ad", ("structured",)),
    "reasoning": (("default", "off", "low", "medium", "high"), "default", ()),
}
TOLD = ("malicious", "benign")
OPTION_DEFAULTS = {
    "samples": 4, "seed": 0, "bin_size": 6, "margin_tokens": 512, "truncate_chars": 2000, "labels": True,
    "max_attempts": 2, "single_pass_if_fits": True, "prep_samples": 3, "concurrency": 8,
    "keep_monitor_reasoning": False, "chunk_tokens": None, "item_limit": 0,
}
# Options that do not change what a single unit's result is (they only change how many units run, or how fast).
NON_IDENTITY_OPTIONS = {"samples", "concurrency", "keep_monitor_reasoning", "item_limit"}
TOP_KEYS = {"name", "monitor", "monitors", "rollout_sets", "told", "grid", "options", "notes"}


@dataclass(frozen=True)
class Spec:
    name: str
    monitors: tuple
    rollout_sets: tuple
    told: tuple
    axes: dict
    options: dict
    raw: dict


@dataclass(frozen=True)
class Cell:
    cell_id: str
    monitor: str
    label: dict   # every axis value, for tables and file names
    params: dict  # parameters handed to monitor_experiment.hierarchy
    options: dict
    partial_cot: dict  # {} when off, else {"mode": "turns"|"tokens", "value": p}


def parse_partial_cot(value):
    if value == "off":
        return {}
    mode, _, number = str(value).partition(":")
    try:
        p = float(number)
    except ValueError:
        raise SpecError(f"partial_cot {value!r}: expected 'off', 'turns:<p>' or 'tokens:<p>'") from None
    if mode not in ("turns", "tokens") or not 0 < p <= 1:
        raise SpecError(f"partial_cot {value!r}: expected 'turns:<p>' or 'tokens:<p>' with 0 < p <= 1")
    return {"mode": mode, "value": p}


def apply_overrides(raw, overrides):
    """Apply ``--set path=value`` overrides (TOML values) to a parsed spec dictionary."""
    raw = _copy(raw)
    for item in overrides:
        path, sep, text = item.partition("=")
        if not sep or not path:
            raise SpecError(f"Override {item!r}: expected path=value, e.g. grid.scope=cot")
        try:
            value = tomllib.loads(f"v = {text}")["v"]
        except tomllib.TOMLDecodeError:
            value = text  # a bare word such as cot
        keys = path.split(".")
        table = raw
        for key in keys[:-1]:
            table = table.setdefault(key, {})
        if keys[0] == "grid" and not isinstance(value, list):
            value = [value]
        table[keys[-1]] = value
    return raw


def _copy(value):
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy(v) for v in value]
    return value


def load_spec(path, overrides=()):
    path = Path(path)
    if not path.is_file():
        raise SpecError(f"Experiment file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise SpecError(f"{path}: {error}") from error
    return parse_spec(apply_overrides(raw, overrides))


def parse_spec(raw):
    extra = set(raw) - TOP_KEYS
    if extra:
        raise SpecError(f"Unknown top-level keys {sorted(extra)}; allowed: {sorted(TOP_KEYS)}")
    for key in ("name", "rollout_sets"):
        if key not in raw:
            raise SpecError(f"Missing required key {key!r}")
    if ("monitor" in raw) == ("monitors" in raw):
        raise SpecError("Give exactly one of 'monitor' (a name) or 'monitors' (a list)")
    monitors = tuple([raw["monitor"]] if "monitor" in raw else raw["monitors"])
    sets = tuple(raw["rollout_sets"])
    if not monitors or not sets or not all(isinstance(x, str) for x in monitors + sets):
        raise SpecError("'monitor(s)' and 'rollout_sets' must be non-empty lists of names")
    told = tuple(raw.get("told", TOLD))
    if not told or any(t not in TOLD for t in told):
        raise SpecError(f"told must be a non-empty subset of {TOLD}, got {list(told)}")
    grid = raw.get("grid", {})
    extra = set(grid) - set(AXES)
    if extra:
        raise SpecError(f"Unknown grid axes {sorted(extra)}; known: {sorted(AXES)}")
    axes = {}
    for name, (allowed, default, unimplemented) in AXES.items():
        values = list(grid.get(name, [] if default is None else [default]))
        if not values:
            raise SpecError(f"grid.{name} is required (allowed: {list(allowed)})")
        if len(set(map(str, values))) != len(values):
            raise SpecError(f"grid.{name} lists a value twice: {values}")
        for value in values:
            if name == "partial_cot":
                parse_partial_cot(value)
            elif value in unimplemented:
                raise SpecError(f"grid.{name} = {value!r} is planned but not implemented yet")
            elif value not in allowed:
                raise SpecError(f"grid.{name} = {value!r} is not one of {list(allowed)}")
        axes[name] = values
    options = dict(OPTION_DEFAULTS)
    extra = set(raw.get("options", {})) - set(OPTION_DEFAULTS)
    if extra:
        raise SpecError(f"Unknown options {sorted(extra)}; known: {sorted(OPTION_DEFAULTS)}")
    options.update(raw.get("options", {}))
    if options["samples"] < 1 or options["concurrency"] < 1 or options["prep_samples"] < 1 or options["item_limit"] < 0:
        raise SpecError("samples, concurrency and prep_samples must be at least 1 and item_limit at least 0")
    return Spec(raw["name"], monitors, sets, told, axes, options, raw)


def expand(spec, registry, fingerprints):
    """Cross product of monitors and axes. ``fingerprints`` holds prompt-file and tokenizer hashes."""
    cells = []
    for name in spec.monitors:
        monitor = registry.monitor(name)
        names = list(AXES)
        for combo in itertools.product(*(spec.axes[a] for a in names)):
            axes = dict(zip(names, combo))
            cells.append(_make_cell(spec, monitor, axes, fingerprints))
    ids = [c.cell_id for c in cells]
    if len(ids) != len(set(ids)):
        raise SpecError("Two cells have identical settings")
    return cells


def _make_cell(spec, monitor, axes, fingerprints):
    preset = dict(HIERARCHY_PRESETS[axes["hierarchy"]])
    if spec.options["chunk_tokens"] is not None:
        preset["chunk_tokens"] = spec.options["chunk_tokens"]
    if preset["context_tokens"] > monitor.context_tokens:
        raise SpecError(f"hierarchy {axes['hierarchy']!r} needs {preset['context_tokens']} tokens of context but "
                        f"monitor {monitor.name!r} is registered with {monitor.context_tokens}")
    if monitor.sampling["max_tokens"] > preset["output_reserve"]:
        raise SpecError(f"monitor {monitor.name!r} may generate {monitor.sampling['max_tokens']} tokens, more than the "
                        f"preset's output reserve {preset['output_reserve']}")
    if axes["reasoning"] in ("low", "medium", "high") and monitor.reasoning_control.get("kind") != "reasoning_effort":
        raise SpecError(f"reasoning = {axes['reasoning']!r} needs a monitor with reasoning_control.kind = 'reasoning_effort'; "
                        f"{monitor.name!r} has {monitor.reasoning_control or 'none'}")
    if axes["reasoning"] == "off" and not monitor.thinking:
        raise SpecError(f"reasoning = 'off' is meaningless for {monitor.name!r}, which does not think")
    params = h.default_params(axes["scope"])
    params.update(preset)
    for key in ("bin_size", "margin_tokens", "truncate_chars", "labels", "max_attempts", "single_pass_if_fits"):
        params[key] = spec.options[key]
    try:
        h.check_params(params)
    except ValueError as error:
        raise SpecError(str(error)) from error
    behavior = {k: v for k, v in spec.options.items() if k not in NON_IDENTITY_OPTIONS and k != "chunk_tokens"}
    label = {"monitor": monitor.name, **axes}
    identity = {"monitor": monitor.identity(), "axes": axes, "params": params, "options": behavior,
                "fingerprints": fingerprints}
    return Cell(digest(identity), monitor.name, label, params, behavior, parse_partial_cot(axes["partial_cot"]))
