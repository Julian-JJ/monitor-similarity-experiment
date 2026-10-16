#!/usr/bin/env python3
"""Download Qwen3-14B on the target cluster, resolving a revision before fetching."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor_experiment.artifacts import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(ROOT / "models/qwen3-14b"))
    parser.add_argument("--revision", default="main", help="Branch/tag or immutable Hugging Face commit")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    try:
        from huggingface_hub import HfApi, snapshot_download
        from importlib.metadata import version
    except ImportError:
        parser.error("Install requirements-download.txt first (or run scripts/setup.sh)")
    model = "Qwen/Qwen3-14B"
    output = Path(args.output_dir).expanduser().resolve()
    revision = HfApi().model_info(model, revision=args.revision).sha
    print(f"Downloading {model}@{revision} to {output}", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    (output / ".download-incomplete").write_text(revision + "\n")
    snapshot_download(repo_id=model, revision=revision, local_dir=output,
                      max_workers=args.workers,
                      allow_patterns=["*.json", "*.safetensors", "*.jinja", "*.txt", "*.model", "*.md", "LICENSE*"])
    # Published only after the entire snapshot has been downloaded successfully.
    write_json(output / "download-manifest.json", {
        "schema_version": 1, "model_id": model, "revision": revision,
        "huggingface_hub_version": version("huggingface-hub"),
        "files": {str(p.relative_to(output)): p.stat().st_size for p in sorted(output.rglob("*"))
                  if p.is_file() and ".cache" not in p.relative_to(output).parts
                  and p.name not in ("download-manifest.json", "serving-manifest.json", ".download-incomplete")}})
    (output / ".download-incomplete").unlink()
    print("Download complete. Immutable revision recorded in download-manifest.json.")


if __name__ == "__main__":
    main()
