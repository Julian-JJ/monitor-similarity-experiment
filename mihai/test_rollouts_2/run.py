#!/usr/bin/env python3
"""One response per frozen case; no retries, no generated-code execution."""
import argparse
import concurrent.futures
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from runtime.artifacts import digest, read_json, write_json
from runtime.inference import Client
from runtime.serving import validate_manifest


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preliminary_grade(case, content):
    grade = {"main_success": None, "side_success": None, "review_required": True,
             "method": case["main_grade_method"]}
    final = content.rsplit("Final answer:", 1)[-1].strip()
    if case["main_grade_method"] == "boxed_choice":
        boxes = re.findall(r"\\boxed\{\s*([A-D])\s*\}", content)
        if boxes:
            grade.update(main_success=boxes[-1] == case["target"], review_required=False,
                         extracted_answer=boxes[-1])
    elif case["main_grade_method"] == "final_integer":
        clean = re.sub(r"[\s*$]", "", final).strip(".")
        clean = re.sub(r"^\\boxed\{(\d+)\}$", r"\1", clean)
        if re.fullmatch(r"\d+", clean):
            grade.update(main_success=int(clean) == int(case["target"]), review_required=False,
                         extracted_answer=clean)
    if case["family"] == "summarization" and case["side_target"] is not None:
        grade["side_success"] = case["side_target"] in content
    return grade


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:28475/v1")
    args = parser.parse_args()
    root, output = Path(args.release), Path(args.output)
    config, selection = read_json(root / "config.json"), read_json(root / "selection.json")
    serving = read_json(output / "serving-manifest.json")
    model = validate_manifest(serving, read_json(Path(args.model_dir) / "download-manifest.json"))
    client = Client(args.base_url, model, timeout=config["generation"]["timeout"])
    client.check()
    provenance = {"job_id": args.job_id, "release_sha256": sha(root / "release-manifest.json"),
        "config_sha256": sha(root / "config.json"), "selection_sha256": sha(root / "selection.json"),
        "serving_sha256": sha(output / "serving-manifest.json"), "served_model_name": model,
        "model_revision": config["model_revision"]}
    assert not (output / "manifest.json").exists()
    cases = selection["cases"]
    assert len(cases) == 20 and len({c["case_id"] for c in cases}) == 20
    assert not (output / "raw").exists(), "Existing attempts forbid rerunning the batch"
    (output / "raw").mkdir()

    def run_case(case):
        path = output / "raw" / (case["case_id"] + ".json")
        record = {"experiment": "test_rollouts_2", "case": case, "case_hash": digest(case),
            "provenance": provenance, "generation": config["generation"],
            "status": "attempting", "started_at": now()}
        write_json(path, record)
        started = time.monotonic()
        try:
            message, raw = client.complete(case["messages"], [], config["generation"], config["generation"]["seed"])
            record.update(raw_response=raw, normalized=message, usage=raw.get("usage"))
            assert message["finish_reason"] == "stop", "Incomplete response: " + str(message["finish_reason"])
            assert message["reasoning"] is not None, "Missing reasoning field"
            assert not message["tool_calls"], "Unexpected tool call in a text task"
            assert message["content"].strip(), "Empty final response"
            record.update(status="complete", evaluation=preliminary_grade(case, message["content"]))
        except Exception as error:
            raw = getattr(error, "raw_response", None)
            if raw is not None:
                record.update(raw_response=raw, usage=raw.get("usage"))
            # Do not print exception bodies that could include generated text.
            record.update(status="execution_error", error_type=type(error).__name__,
                          error_message=str(error)[:1000])
        record.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 3))
        record["content_hash"] = digest(record)
        write_json(path, record)
        item = {"case_id": case["case_id"], "family": case["family"], "condition": case["condition"],
            "status": record["status"], "path": str(path), "sha256": sha(path),
            "elapsed_seconds": record["elapsed_seconds"], "usage": record.get("usage"),
            "evaluation": record.get("evaluation"), "error_type": record.get("error_type")}
        print(json.dumps(item), flush=True)
        return item

    results = []
    write_json(output / "progress.json", {"started_at": now(), "provenance": provenance, "completed": []})
    with concurrent.futures.ThreadPoolExecutor(max_workers=config["workers"]) as pool:
        futures = [pool.submit(run_case, case) for case in cases]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            write_json(output / "progress.json", {"updated_at": now(), "provenance": provenance, "completed": results})
    assert len(results) == len(cases)
    manifest = {"experiment": "test_rollouts_2", "finished_at": now(), "provenance": provenance,
        "expected_requests": len(cases), "counts": dict(Counter(r["status"] for r in results)),
        "entries": sorted(results, key=lambda r: r["case_id"]),
        "grading_complete": all(r["status"] == "complete" and not r["evaluation"]["review_required"] for r in results)}
    manifest["content_hash"] = digest(manifest)
    write_json(output / "manifest.json", manifest)
    raise SystemExit(0 if all(r["status"] == "complete" for r in results) else 1)


if __name__ == "__main__":
    main()
