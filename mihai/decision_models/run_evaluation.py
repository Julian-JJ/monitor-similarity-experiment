"""Actions or CoT GLiDE evaluation using the baseline's loader, renderer and metrics.

prepare: verify files and count every prompt, without GPU inference.
run: one GLiDE call per case, four sampled letters, plus its default decision.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
import time

# This script is shipped inside a pinned copy of the baseline repository.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from monitor_experiment import hierarchy as h, metrics
from monitor_experiment.artifacts import digest, lock, read_json, write_json
from monitor_experiment.data import RolloutSet, ObjectiveTable, make_pairs
from monitorbench_glide import make_request
from sampling import sampling_distribution, draw_answers


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_source():
    manifest = read_json(ROOT / "source-manifest.json")
    actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()}
    if actual != set(manifest["files"]) | {"source-manifest.json"}:
        raise ValueError("Frozen source inventory changed")
    for name, expected in manifest["files"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError(f"Frozen source changed: {name}")


def load_items(config):
    collections = [RolloutSet.from_manifest(name, entry["root"], verify=True)
                   for name, entry in config["collections"].items()]
    for collection in collections:
        if len(collection.items) != config["collections"][collection.name]["count"]:
            raise ValueError(f"Unexpected collection size: {collection.name}")
        if collection.manifest_sha256 != config["collections"][collection.name]["sha256"]:
            raise ValueError(f"Collection manifest changed: {collection.name}")
    items = sorted([item for collection in collections for item in collection.items],
                   key=lambda item: item.item_id)
    if len({item.item_id for item in items}) != len(items):
        raise ValueError("Duplicate rollout identity across collections")
    return collections, items


def prepare(config, output):
    verify_source()
    if (output / "ready.json").exists():
        raise ValueError("This run already has prepared inputs; do not overwrite them")
    model_dir = Path(config["model_dir"])
    manifest = read_json(model_dir / "download-manifest.json")
    if manifest["revision"] != config["model_revision"]:
        raise ValueError("Wrong model revision")
    for entry in manifest["files"]:
        if file_hash(model_dir / entry["path"]) != entry["sha256"]:
            raise ValueError(f"Model file changed: {entry['path']}")
    collections, items = load_items(config)
    objectives = ObjectiveTable.from_json(ROOT / "configs/objectives.json")
    if objectives.texts != ObjectiveTable.build(items).texts:
        raise ValueError("Objectives differ from the baseline's frozen table")

    # Render GLiDE's exact prompt with its tokenizer; no model weights are loaded.
    from transformers import AutoTokenizer
    prompt_code = runpy.run_path(str(model_dir / "glide/prompt.py"))
    model_config = read_json(model_dir / "decision_config.json")
    if model_config.get("temperature", 1.0) != 1.0:
        raise ValueError("Review probability scaling before applying another temperature")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    prompter = prompt_code["Prompter"](tokenizer, model_config["codes"])
    cases, lengths = [], []
    for item in items:
        observation = item.observation()  # Excludes system instructions and all grader labels.
        parts, cuts = [], 0
        for turn in h.turns(observation.messages):
            header, body, cut = h.render_turn(turn, config["scope"], labels=True, truncate_chars=2000)
            if body.strip():
                parts.append(header + "\n" + body)
            cuts += cut
        text = "\n\n".join(parts)
        for told in ("malicious", "benign"):
            request = make_request(observation.main_task, objectives.text(item.task, told), text, config["scope"])
            question = request["questions"]["verdict"]
            prompt = prompter.text(request["state"], question, prompt_code["options_for"](question))
            length = len(tokenizer(prompt, add_special_tokens=False)["input_ids"])
            lengths.append(length)
            cases.append({"item_id": item.item_id, "told": told, "request": request,
                          "request_sha256": digest(request), "prompt_tokens": length,
                          "truncated_tool_results": cuts})
    if "expected_lengths_path" in config:
        # Confirm full CoT inputs match the already-audited pilot's length inventory.
        path = Path(config["expected_lengths_path"])
        assert file_hash(path) == config["expected_lengths_sha256"]
        expected = {(r["item_id"], r["told"]): r["tokens"] for r in read_json(path)["cases"]}
        actual = {(r["item_id"], r["told"]): r["prompt_tokens"] for r in cases}
        assert actual == expected, "Full prompt lengths differ from the pilot"
    summary = {"config_sha256": digest(config), "rollouts": len(items), "cases": len(cases),
               "source_manifest_sha256": file_hash(ROOT / "source-manifest.json"),
               "min_prompt_tokens": min(lengths), "max_prompt_tokens": max(lengths),
               "over_limit": sum(n + 8 > config["max_context"] for n in lengths),
               "collection_hashes": {c.name: c.manifest_sha256 for c in collections}}
    write_json(output / "preflight.json", summary)
    print(json.dumps(summary), flush=True)
    if summary["over_limit"]:
        raise ValueError("Some full inputs do not fit; no GPU evaluation was started")
    write_json(output / "inputs.json", cases)  # Raw inputs stay on cluster storage.
    write_json(output / "ready.json", {**summary, "inputs_sha256": file_hash(output / "inputs.json")})


def score(config, output, cases):
    collections, items = load_items(config)
    ready = read_json(output / "ready.json")
    if {c.name: c.manifest_sha256 for c in collections} != ready["collection_hashes"]:
        raise ValueError("Collection manifest changed since preflight")
    pairs = {pair.key: pair for pair in make_pairs(items)}
    sampled, greedy = [], []
    for index, case in enumerate(cases):
        result = read_json(output / "pairs" / f"{index:03d}.json")
        base = {"item_id": case["item_id"], "told": case["told"], "status": result["status"]}
        for draw in result.get("draws", [{"sample": s, "letter": None} for s in range(4)]):
            sampled.append({**base, **draw, "detected": draw["letter"] == "A" if draw["letter"] else None})
        letter = result.get("greedy_letter")
        greedy.append({**base, "sample": 0, "letter": letter,
                       "detected": letter == "A" if letter else None})
    for name, records in (("sampled", sampled), ("greedy", greedy)):
        collected = metrics.collect(records, pairs)
        points = metrics.point_estimates(collected, pairs)
        write_json(output / f"{name}-records.json", records)
        write_json(output / f"{name}-metrics.json", {
            "point_estimates": points,
            "intervals": metrics.bootstrap_intervals(collected, pairs, n=2000, seed=0)})
    complete = sum(row["status"] == "complete" for row in greedy)
    summary = {"cases": len(cases), "complete": complete, "failed": len(cases) - complete,
               "sampled_judgments": len(sampled), "greedy_judgments": len(greedy)}
    write_json(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


def evaluate(config, output):
    verify_source()
    ready = read_json(output / "ready.json")
    if ready["config_sha256"] != digest(config) or file_hash(output / "inputs.json") != ready["inputs_sha256"]:
        raise ValueError("Prepared inputs or configuration changed")
    cases = read_json(output / "inputs.json")
    sys.path.insert(0, config["model_dir"])
    import torch
    from glide import Glide
    write_json(output / "hardware.json", {"gpu": torch.cuda.get_device_name(),
               "torch": torch.__version__, "cuda": torch.version.cuda, "job_id": os.environ.get("SLURM_JOB_ID")})
    model = Glide.from_pretrained(config["model_dir"], vision=False, max_len=config["max_context"])
    if model.temperature != 1.0:
        raise ValueError("Model probability temperature changed")
    # A short case first, then the longest, so long-input problems surface early.
    order = sorted(range(len(cases)), key=lambda i: cases[i]["prompt_tokens"])
    order = [order[0], order[-1]] + order[1:-1]
    for index in order:
        case = cases[index]
        path = output / "pairs" / f"{index:03d}.json"
        if path.exists():
            saved = read_json(path)
            if saved["request_sha256"] != case["request_sha256"] or saved["config_sha256"] != digest(config):
                raise ValueError("Saved result belongs to a different request or run")
            continue
        result = {"item_id": case["item_id"], "told": case["told"],
                  "request_sha256": case["request_sha256"], "config_sha256": digest(config)}
        torch.cuda.synchronize()  # Wait for GPU work before starting the timer.
        torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        try:
            response = model.decide(**case["request"])
            torch.cuda.synchronize()
            assert response["usage"] == {"input_tokens": case["prompt_tokens"], "output_tokens": 0}
            answer = response["answers"]["verdict"]
            probabilities = answer["probabilities"]
            distribution = sampling_distribution(probabilities, config["temperature"], config["top_p"])
            winner = max("ABCD", key=lambda letter: probabilities[letter])
            if answer["type"] != "choice" or answer["choice"] != winner:
                raise ValueError("Invalid choice response")
            result.update(status="complete", response=response, sampling_probabilities=distribution,
                          greedy_letter=winner, draws=draw_answers(distribution,
                          f"{case['item_id']}:{case['told']}", config["seed"], config["samples"]))
        except Exception as error:
            # A failed call remains failed, never a negative verdict; no automatic retry.
            result.update(status="failed", error_type=type(error).__name__, error=str(error)[:1000])
            if isinstance(error, torch.cuda.OutOfMemoryError):
                torch.cuda.empty_cache()
        result["seconds"] = time.monotonic() - started
        result["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        result["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
        write_json(path, result)
        print(json.dumps({"case": index, "item_id": case["item_id"], "told": case["told"],
                          "status": result["status"], "seconds": result["seconds"]}), flush=True)
    summary = score(config, output, cases)
    if summary["failed"]:
        raise RuntimeError("Evaluation finished with failed cases; see summary.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["prepare", "run"])
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = read_json(args.config)
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / "evaluation.lock"):
        if args.stage == "prepare":
            prepare(config, output)
        else:
            evaluate(config, output)
