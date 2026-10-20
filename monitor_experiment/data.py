"""Frozen rollout collections: verified loading, and the split between observable data and labels.

A *collection* is a directory with a ``manifest.json`` that lists complete actor
rollouts and their checksums (the format of ``rollouts_original_clean/``). Loading
verifies every checksum. An :class:`Item` hands a monitor only an :class:`Observation`
(the task and the assistant and tool messages, never the system prompt); the labels
are a separate object that only scoring code asks for.

A *pair* is an item judged under one told objective (the malicious or the benign
side objective of its task). Its label is the recorded outcome for that objective,
and its *role* says what kind of evidence the pair is. See docs/system/data-layer.md.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import hierarchy as h
from .artifacts import read_json, write_json

OBJECTIVES = ("malicious", "benign")
VARIANTS = ("malicious", "benign", "main_only")
ROLES = ("positive", "clean_negative", "cross_negative", "own_failure")


class DataError(RuntimeError):
    """A collection or objective table is missing, inconsistent or tampered with."""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Observation:
    """Everything a monitor may see about one rollout. No system prompt, labels or state."""
    item_id: str
    task: str
    main_task: str
    messages: tuple  # the user message, then assistant and tool messages


@dataclass(frozen=True)
class Labels:
    """Recorded outcomes. Privileged: used only to score, never to build a prompt."""
    malicious: bool
    benign: bool
    main_success: bool

    def for_objective(self, told):
        if told not in OBJECTIVES:
            raise ValueError(f"Unknown objective {told!r}; expected one of {OBJECTIVES}")
        return self.malicious if told == "malicious" else self.benign


@dataclass
class Item:
    item_id: str
    task: str
    variant: str
    sample: int
    rollout_id: str
    path: Path
    followup_path: Path
    source_job: str = None
    hardware: str = None
    termination: str = None
    turns: int = None
    set_name: str = None
    _raw: dict = field(default=None, repr=False, compare=False)

    @property
    def origin(self):
        """``control`` for ``main_only`` rollouts, ``cached`` for the original batch."""
        return "control" if self.variant == "main_only" else "cached"

    @property
    def group(self):
        """Stratum used by the bootstrap: rollouts are resampled within their group."""
        return f"{self.origin}/{self.variant}/{self.task}"

    def raw(self):
        if self._raw is None:
            self._raw = read_json(self.path)
        return self._raw

    def observation(self):
        messages = tuple(m for m in self.raw()["messages"] if m["role"] != "system")
        return Observation(self.item_id, self.task, h.main_task(messages), messages)

    def labels(self):
        evaluation = self.raw()["evaluation"]
        side = evaluation["side"]
        return Labels(bool(side["malicious"]), bool(side["benign"]), bool(evaluation["main"]["success"]))

    def embedded_objective(self):
        """The side-objective text in this rollout's own system message; ``None`` for controls."""
        if self.variant == "main_only":
            return None
        return h.hidden_objective(self.raw()["messages"])

    def followup(self):
        return read_json(self.followup_path)


def make_item_id(task, variant, sample):
    return f"{task}/{variant}/sample_{int(sample):02d}"


@dataclass
class RolloutSet:
    name: str
    root: Path
    items: list
    manifest_sha256: str
    verified: bool

    def by_id(self):
        return {item.item_id: item for item in self.items}

    @classmethod
    def from_manifest(cls, name, root, manifest="manifest.json", verify=True):
        root = Path(root)
        manifest_path = root / manifest
        if not manifest_path.is_file():
            raise DataError(f"Collection {name!r}: no manifest at {manifest_path}")
        data = read_json(manifest_path)
        items, problems = [], []
        for pair in data["pairs"]:
            ident = make_item_id(pair["task"], pair["variant"], pair["sample"])
            rollout, followup = root / pair["actor"], root / pair["followup"]
            if verify:
                for label, path, key in (("rollout", rollout, "actor_sha256"), ("follow-up", followup, "followup_sha256")):
                    if not path.is_file():
                        problems.append(f"{ident}: {label} file missing ({path})")
                    elif sha256_file(path) != pair[key]:
                        problems.append(f"{ident}: {label} checksum differs from the manifest")
            item = Item(ident, pair["task"], pair["variant"], int(pair["sample"]), pair["rollout_id"], rollout, followup,
                        pair.get("source_job_id"), pair.get("hardware"), pair.get("termination"), pair.get("turns"), name)
            items.append(item)
        if verify and not problems:
            for item in items:
                raw = item.raw()
                if raw.get("status") != "complete" or raw.get("rollout_id") != item.rollout_id:
                    problems.append(f"{item.item_id}: not a complete rollout with the manifest's rollout id")
                if item.variant not in VARIANTS:
                    problems.append(f"{item.item_id}: unknown variant {item.variant!r}")
        if problems:
            raise DataError(f"Collection {name!r} failed verification:\n  " + "\n  ".join(problems))
        ids = [i.item_id for i in items]
        if len(ids) != len(set(ids)):
            raise DataError(f"Collection {name!r} lists the same rollout twice")
        return cls(name, root, items, sha256_file(manifest_path), verify)


class ObjectiveTable:
    """The text of each side objective, per task and objective.

    Each (task, objective) has exactly one text across all samples of a collection
    (checked when the table is built). Controls have no objective in their own system
    message; they, and rollouts judged under the *other* objective, take the text from here.
    """

    def __init__(self, texts):
        self.texts = dict(texts)

    def text(self, task, objective):
        try:
            return self.texts[(task, objective)]
        except KeyError:
            raise DataError(f"No objective text for task {task!r}, objective {objective!r}") from None

    @classmethod
    def build(cls, items):
        found, counts = {}, {}
        for item in items:
            if item.variant == "main_only":
                continue
            key = (item.task, item.variant)
            text = item.embedded_objective()
            found.setdefault(key, set()).add(text)
            counts[key] = counts.get(key, 0) + 1
        conflicts = [key for key, texts in found.items() if len(texts) != 1]
        if conflicts:
            raise DataError(f"More than one objective text for {conflicts}; the table needs one per task and objective")
        table = cls({key: next(iter(texts)) for key, texts in found.items()})
        table.counts = counts
        return table

    def to_json(self, path, source):
        entries = [{"task": task, "objective": objective, "text": text,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(), "characters": len(text),
                    "samples_seen": getattr(self, "counts", {}).get((task, objective))}
                   for (task, objective), text in sorted(self.texts.items())]
        write_json(path, {"schema_version": 1, "source": source, "entries": entries})

    @classmethod
    def from_json(cls, path):
        data = read_json(path)
        texts = {}
        for entry in data["entries"]:
            if hashlib.sha256(entry["text"].encode()).hexdigest() != entry["sha256"]:
                raise DataError(f"Objective text for {entry['task']}/{entry['objective']} does not match its checksum")
            texts[(entry["task"], entry["objective"])] = entry["text"]
        return cls(texts)


def pair_role(variant, told, label):
    """What kind of evidence a (rollout, told objective) pair is.

    ``positive``: the agent achieved the told objective (whatever its variant).
    ``clean_negative``: a control rollout (no hidden objective) that did not achieve it.
    ``cross_negative``: the agent was told to pursue the *other* objective.
    ``own_failure``: the agent was told to pursue this objective and missed it.
    """
    if told not in OBJECTIVES or variant not in VARIANTS:
        raise ValueError(f"Unknown variant {variant!r} or objective {told!r}")
    if label:
        return "positive"
    if variant == "main_only":
        return "clean_negative"
    return "own_failure" if told == variant else "cross_negative"


@dataclass(frozen=True)
class Pair:
    item_id: str
    told: str
    label: bool
    role: str
    task: str
    variant: str
    origin: str
    group: str

    @property
    def key(self):
        return (self.item_id, self.told)


def make_pairs(items, told=OBJECTIVES):
    """Every item under every told objective, with its label and role."""
    pairs = []
    for item in items:
        labels = item.labels()
        for objective in told:
            label = labels.for_objective(objective)
            pairs.append(Pair(item.item_id, objective, label, pair_role(item.variant, objective, label),
                              item.task, item.variant, item.origin, item.group))
    return pairs
