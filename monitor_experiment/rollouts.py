"""Sequential agent execution, resumable state checkpoints, and follow-up branches."""

import ast
import copy
import fcntl
import importlib.metadata
import json
import platform
import random
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .artifacts import digest, read_json, write_json
from .environments import Environment, ROOT, provenance

FOLLOWUP = (ROOT / "prompts/generic_followup.txt").read_text().strip()


def now():
    return datetime.now(timezone.utc).isoformat()


def versions():
    return {name: importlib.metadata.version(name) for name in
            ("pydantic", "pandas", "PyYAML", "docstring-parser", "typing-extensions")}


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"Another worker owns {path}") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def add_message(messages, message):
    messages.append({"id": f"m{len(messages):05d}", **message})


def validate_completion(message, require_reasoning):
    if message["finish_reason"] not in ("stop", "tool_calls"):
        raise ValueError(f"Incomplete generation: finish_reason={message['finish_reason']!r}")
    if require_reasoning and not message.get("reasoning"):
        raise ValueError("No reasoning returned; use Qwen thinking mode and --reasoning-parser qwen3")


def run_actor(client, path, identity, settings, environment_factory=Environment):
    """Resume after the last committed turn, including simulated state and RNG."""
    task, variant, seed = (identity[k] for k in ("task", "variant", "seed"))
    environment = environment_factory(task, variant, seed)
    if path.exists():
        artifact = read_json(path)
        if artifact["identity"] != identity:
            raise ValueError("Cache identity mismatch")
        if artifact["status"] == "complete":
            return artifact
        environment.restore(artifact["final_state"])
        random.setstate(ast.literal_eval(artifact["random_state"]))
    else:
        initial = environment.snapshot()
        artifact = {"schema_version": 1, "artifact_type": "actor_rollout",
                    "rollout_id": digest(identity), "identity": identity,
                    "created_at": now(), "status": "running", "messages": [],
                    "initial_state_hash": digest(initial), "initial_state": initial,
                    "raw_responses": [], "turns": 0, "elapsed_seconds": 0.0,
                    "actor_finished": False, "evaluation": None}
        for message in environment.prompts():
            add_message(artifact["messages"], message)

    def checkpoint():
        artifact["final_state"] = environment.snapshot()
        artifact["random_state"] = repr(random.getstate())
        artifact["updated_at"] = now()
        write_json(path, artifact)

    checkpoint()
    artifact.pop("error", None)
    artifact["status"] = "running"
    try:
        while not artifact["actor_finished"] and artifact["turns"] < settings["max_turns"]:
            started = time.monotonic()
            message, raw = client.complete(artifact["messages"], environment.tools(), settings,
                                           seed + artifact["turns"])
            # Validate before mutating environment. Failed responses are preserved
            # separately and do not become part of a resumed conversation.
            try:
                validate_completion(message, settings["require_reasoning"])
            except ValueError:
                artifact.setdefault("failed_responses", []).append(raw)
                raise
            artifact["raw_responses"].append(raw)
            add_message(artifact["messages"], message)
            ended = False
            for call in message["tool_calls"]:
                name = call["function"]["name"]
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be an object")
                    if ended:
                        result, error = None, "Task already ended; tool was not executed"
                    else:
                        result, error = environment.execute(name, arguments)
                except (ValueError, TypeError) as exception:
                    result, error = None, f"Invalid tool arguments: {exception}"
                if name == "end_task" and error is None:
                    ended = True
                add_message(artifact["messages"], {
                    "role": "tool", "tool_call_id": call["id"], "name": name,
                    "content": error if error else (result if isinstance(result, str)
                               else json.dumps(result, ensure_ascii=False, default=str)),
                    "error": error})
            artifact["turns"] += 1
            artifact["elapsed_seconds"] += time.monotonic() - started
            artifact["actor_finished"] = ended or not message["tool_calls"]
            if artifact["actor_finished"]:
                artifact["termination"] = "end_task" if ended else "final_answer"
            checkpoint()
        if not artifact["actor_finished"]:
            artifact["termination"] = "max_turns"
        artifact["evaluation"] = environment.evaluate()
        artifact["status"] = "complete"
        checkpoint()
        return artifact
    except Exception as exception:
        raw = getattr(exception, "raw_response", None)
        if raw is not None:
            artifact.setdefault("failed_responses", []).append(raw)
        artifact["status"] = "error"
        artifact["error"] = {"type": type(exception).__name__, "message": str(exception)}
        checkpoint()
        raise


def run_followup(client, path, actor, identity, settings):
    if path.exists():
        previous = read_json(path)
        if previous["identity"] != identity:
            raise ValueError("Follow-up cache identity mismatch")
        if previous["status"] == "complete":
            return previous
    # No tools are passed or executed; each sample branches from the original end.
    messages = copy.deepcopy(actor["messages"])
    add_message(messages, {"role": "user", "content": FOLLOWUP})
    artifact = {"schema_version": 1, "artifact_type": "followup",
                "followup_id": digest(identity), "identity": identity,
                "parent_rollout_id": actor["rollout_id"], "created_at": now(),
                "status": "running", "question": FOLLOWUP}
    started = time.monotonic()
    try:
        message, raw = client.complete(messages, [], settings, identity["seed"])
        artifact["raw_response"] = raw
        validate_completion(message, settings["require_reasoning"])
        if message["tool_calls"]:
            raise ValueError("Follow-up returned tool calls despite tools being disabled")
        add_message(messages, message)
        artifact["response"] = messages[-1]
        artifact["status"] = "complete"
    except Exception as exception:
        raw = getattr(exception, "raw_response", None)
        if raw is not None:
            artifact["raw_response"] = raw
        artifact["status"] = "error"
        artifact["error"] = {"type": type(exception).__name__, "message": str(exception)}
        raise
    finally:
        artifact["elapsed_seconds"] = time.monotonic() - started
        write_json(path, artifact)
    return artifact


def generate(config, client, cache, tasks, variants, samples, start=0, environment_factory=Environment):
    cache = Path(cache).resolve()
    source = provenance()
    runtime = {"framework": __version__, "python": platform.python_version(), "packages": versions()}
    # Include local implementation changes without hashing cache/docs/tests.
    runtime["implementation_hash"] = digest({p.name: p.read_text() for p in
                                              sorted((ROOT / "monitor_experiment").glob("*.py"))})
    actor_settings = config["generation"]
    followup_settings = {**actor_settings, "max_tokens": config["followup"]["max_tokens"]}
    entries = []
    for task in tasks:
        for variant in variants:
            for sample in range(start, start + samples):
                seed = actor_settings["seed"] + sample * 100000
                identity = {"task": task, "variant": variant, "sample": sample, "seed": seed,
                            "model": config["model"], "endpoint": client.base_url,
                            "generation": actor_settings, "environment": source, "runtime": runtime}
                rollout_id = digest(identity)
                path = cache / "rollouts" / task / variant / f"{rollout_id}.json"
                with lock(path.with_suffix(".lock")):
                    actor = run_actor(client, path, identity, actor_settings, environment_factory)
                    followups = []
                    for index in range(config["followup"]["samples"]):
                        fid = {"parent": rollout_id, "parent_hash": digest(actor),
                               "prompt": FOLLOWUP, "sample": index,
                               "seed": seed + 50000 + index, "settings": followup_settings}
                        fpath = cache / "followups" / rollout_id / f"{digest(fid)}.json"
                        run_followup(client, fpath, actor, fid, followup_settings)
                        followups.append(str(fpath.relative_to(cache)))
                entry = {"rollout_id": rollout_id, "task": task, "variant": variant,
                         "sample": sample, "rollout": str(path.relative_to(cache)),
                         "followups": followups}
                entries.append(entry)
                # Deterministic per-sample manifests survive interrupted batch runs.
                write_json(cache / "entries" / f"{rollout_id}.json", entry)
                print(f"{task}/{variant} sample={sample}: {actor['termination']}; "
                      f"main={actor['evaluation']['main']['success']} "
                      f"side={actor['evaluation']['side_success']}; {len(followups)} follow-up(s)", flush=True)
    manifest = {"schema_version": 1, "entries": entries}
    path = cache / "manifests" / f"{digest(manifest)}.json"
    write_json(path, manifest)
    print(f"Manifest: {path}", flush=True)
    return path
