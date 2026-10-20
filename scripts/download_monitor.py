#!/usr/bin/env python3
"""Download a registered monitor's weights (``configs/monitors.toml``) into a directory, recording the resolved revision."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor_experiment import monitor_download
from monitor_experiment.registry import Registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("monitor", help="registry name, for example qwen3-32b")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--revision", help="override the registry's pin (a branch or commit); default: the pin, or main if UNPINNED")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--verify-only", action="store_true", help="check an existing download against the registry and exit")
    args = parser.parse_args()
    monitor = Registry.load().monitor(args.monitor)
    if args.verify_only:
        manifest = monitor_download.verify(args.output_dir, monitor)
    else:
        from importlib.metadata import version
        manifest = monitor_download.download(monitor, args.output_dir, revision=args.revision, workers=args.workers,
                                             hub_version=version("huggingface-hub"))
    total = sum(manifest["files"].values())
    print(f"{monitor.model_id}@{manifest['revision']}: {len(manifest['files'])} files, {total / 1e9:.1f} GB")
    if monitor.revision == monitor_download.UNPINNED:
        print(f'Pin it: set revision = "{manifest["revision"]}" in configs/monitors.toml for {args.monitor}')


if __name__ == "__main__":
    main()
