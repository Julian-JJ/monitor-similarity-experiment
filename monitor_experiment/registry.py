"""Registries of monitor models and rollout sets, read from TOML and strictly validated.

``configs/monitors.toml`` lists the monitors an experiment may choose by name;
``configs/rollout_sets.toml`` names the frozen collections and the fixed agent that
produced them. Unknown or missing keys are errors, so a typo cannot silently change
what runs. See docs/system/registries.md.
"""

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from .artifacts import digest
from .data import RolloutSet

ROOT = Path(__file__).resolve().parents[1]
RELATIONS = ("same_model", "same_family_smaller", "same_family_larger",
             "same_family_other_architecture", "different_family")


class RegistryError(ValueError):
    """A registry file is malformed, or an entry cannot be used as requested."""


@dataclass(frozen=True)
class Actor:
    model_id: str
    revision: str
    family: str
    size_b: float
    architecture: str


@dataclass(frozen=True)
class Monitor:
    name: str
    model_id: str
    revision: str
    family: str
    size_b: float
    architecture: str
    provider: str
    open_weights: bool
    base_url: str
    context_tokens: int
    output_reserve: int
    sampling: dict
    thinking: bool
    reasoning_control: dict
    verified: bool
    active_b: float = None
    notes: str = ""
    reasoning_parser: str = None   # vLLM --reasoning-parser name; None serves the thinking inline in the content

    def runnable(self):
        """Raise unless this entry names a concrete model (placeholders start with ``TBD``)."""
        if self.model_id.startswith("TBD"):
            raise RegistryError(f"Monitor {self.name!r} is a placeholder ({self.model_id}); fill in the model first")
        return self

    def identity(self):
        """What makes results from this monitor comparable: everything except where it is served."""
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        for deployment_only in ("base_url", "notes", "verified"):
            data.pop(deployment_only)
        return data

    def relation_to(self, actor):
        """Relation to the fixed agent: same model, same family (smaller, larger, other architecture), other family."""
        if self.model_id == actor.model_id:
            return "same_model"
        if self.family != actor.family:
            return "different_family"
        if self.architecture != actor.architecture:
            return "same_family_other_architecture"
        return "same_family_smaller" if self.size_b < actor.size_b else "same_family_larger"


@dataclass(frozen=True)
class SetEntry:
    name: str
    root: Path
    manifest: str
    status: str
    description: str


MONITOR_REQUIRED = {"model_id", "revision", "family", "size_b", "architecture", "provider", "open_weights",
                    "base_url", "context_tokens", "output_reserve", "thinking", "verified", "sampling"}
MONITOR_OPTIONAL = {"active_b", "notes", "reasoning_control", "reasoning_parser"}
ARCHITECTURES = ("dense", "moe")
SET_KEYS = {"root", "manifest", "status", "description"}
ACTOR_KEYS = {"model_id", "revision", "family", "size_b", "architecture"}
SAMPLING_KEYS = {"temperature", "top_p", "max_tokens"}


def _read(path):
    path = Path(path)
    if not path.is_file():
        raise RegistryError(f"Registry file not found: {path}")
    try:
        return tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as error:
        raise RegistryError(f"{path}: {error}") from error


def _check_keys(where, table, required, optional=()):
    missing, extra = required - set(table), set(table) - required - set(optional)
    if missing:
        raise RegistryError(f"{where}: missing {sorted(missing)}")
    if extra:
        raise RegistryError(f"{where}: unknown keys {sorted(extra)}")


class Registry:
    def __init__(self, monitors, sets, actor, reference_tokenizer, objectives_table):
        self.monitors, self.sets, self.actor = monitors, sets, actor
        self.reference_tokenizer = reference_tokenizer
        self.objectives_table = objectives_table

    @classmethod
    def load(cls, config_dir=None, root=ROOT):
        config_dir = Path(config_dir) if config_dir else root / "configs"
        monitors_file, sets_file = _read(config_dir / "monitors.toml"), _read(config_dir / "rollout_sets.toml")
        _check_keys("monitors.toml", {k: 0 for k in monitors_file}, {"monitors", "reference_tokenizer"})
        monitors = {}
        for name, entry in monitors_file["monitors"].items():
            where = f"monitors.toml [monitors.{name}]"
            _check_keys(where, set_of(entry), MONITOR_REQUIRED, MONITOR_OPTIONAL)
            _check_keys(where + ".sampling", set_of(entry["sampling"]), SAMPLING_KEYS)
            if entry["architecture"] not in ARCHITECTURES:
                raise RegistryError(f"{where}: architecture must be one of {ARCHITECTURES}")
            if entry["output_reserve"] >= entry["context_tokens"]:
                raise RegistryError(f"{where}: output_reserve must be smaller than context_tokens")
            if entry["sampling"]["max_tokens"] > entry["output_reserve"]:
                raise RegistryError(f"{where}: sampling.max_tokens exceeds output_reserve")
            monitors[name] = Monitor(name=name, reasoning_control=dict(entry.get("reasoning_control", {})),
                                     **{k: v for k, v in entry.items() if k != "reasoning_control"})
        _check_keys("rollout_sets.toml", {k: 0 for k in sets_file}, {"actor", "objectives", "sets"})
        _check_keys("rollout_sets.toml [actor]", set_of(sets_file["actor"]), ACTOR_KEYS)
        actor = Actor(**sets_file["actor"])
        sets = {}
        for name, entry in sets_file["sets"].items():
            _check_keys(f"rollout_sets.toml [sets.{name}]", set_of(entry), SET_KEYS)
            if entry["status"] not in ("available", "planned"):
                raise RegistryError(f"rollout_sets.toml [sets.{name}]: status must be 'available' or 'planned'")
            sets[name] = SetEntry(name, root / entry["root"], entry["manifest"], entry["status"], entry["description"])
        return cls(monitors, sets, actor, root / monitors_file["reference_tokenizer"],
                   root / sets_file["objectives"]["table"])

    def monitor(self, name):
        try:
            return self.monitors[name]
        except KeyError:
            raise RegistryError(f"Unknown monitor {name!r}; registry has {sorted(self.monitors)}") from None

    def load_set(self, name, verify=True):
        try:
            entry = self.sets[name]
        except KeyError:
            raise RegistryError(f"Unknown rollout set {name!r}; registry has {sorted(self.sets)}") from None
        if not (entry.root / entry.manifest).is_file():
            hint = " (planned, not generated yet)" if entry.status == "planned" else ""
            raise RegistryError(f"Rollout set {name!r}{hint}: no manifest at {entry.root / entry.manifest}")
        return RolloutSet.from_manifest(name, entry.root, entry.manifest, verify=verify)

    def actor_identity(self):
        return digest(self.actor.__dict__)


def set_of(table):
    return set(table)
