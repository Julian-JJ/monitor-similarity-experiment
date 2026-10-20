"""Download the weights of one registered monitor and record exactly which files and revision arrived. See docs/system/cluster.md.

The pattern follows ``scripts/download_model.py`` (the actor's downloader) but takes the repository from the registry instead of
hard-coding it. The revision is resolved to an immutable commit before anything is fetched; ``.download-incomplete`` exists for
the whole download, and ``download-manifest.json`` is written last, so a directory with the manifest and without the marker is complete.
:func:`verify` is what the server launcher uses to refuse a directory that is not the registered model at the registered revision.
"""

from pathlib import Path

from .artifacts import lock, read_json, write_json

PATTERNS = ["*.json", "*.safetensors", "*.jinja", "*.txt", "*.model", "*.md", "LICENSE*"]
UNPINNED = "UNPINNED"
_NOT_PAYLOAD = ("download-manifest.json", "serving-manifest.json", ".download-incomplete", ".model.lock")


class DownloadError(RuntimeError):
    pass


def file_sizes(output):
    output = Path(output)
    return {str(p.relative_to(output)): p.stat().st_size for p in sorted(output.rglob("*"))
            if p.is_file() and ".cache" not in p.relative_to(output).parts and p.name not in _NOT_PAYLOAD}


def download(monitor, output, *, revision=None, workers=4, resolve=None, fetch=None, hub_version="unknown"):
    """Fetch ``monitor``'s weights into ``output`` and return the manifest.

    ``revision`` defaults to the registry's pin, or to ``main`` while the registry says UNPINNED. ``resolve(repo, revision)`` and
    ``fetch(repo, revision, output, workers)`` are the Hugging Face calls, injectable for tests.
    """
    if monitor.provider != "cluster" or not monitor.open_weights:
        raise DownloadError(f"{monitor.name!r} is not an open-weights cluster monitor; nothing to download")
    wanted = revision or (None if monitor.revision == UNPINNED else monitor.revision) or "main"
    if resolve is None or fetch is None:
        from huggingface_hub import HfApi, snapshot_download
        resolve = resolve or (lambda repo, rev: HfApi().model_info(repo, revision=rev).sha)
        fetch = fetch or (lambda repo, rev, out, n: snapshot_download(repo_id=repo, revision=rev, local_dir=out, max_workers=n,
                                                                       allow_patterns=PATTERNS))
    resolved = resolve(monitor.model_id, wanted)
    if monitor.revision != UNPINNED and resolved != monitor.revision:
        raise DownloadError(f"{monitor.model_id}@{wanted} is {resolved}, but the registry pins {monitor.revision}")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with lock(output / ".model.lock"):
        (output / ".download-incomplete").write_text(resolved + "\n")
        fetch(monitor.model_id, resolved, str(output), workers)
        manifest = {"schema_version": 1, "monitor": monitor.name, "model_id": monitor.model_id, "revision": resolved,
                    "huggingface_hub_version": hub_version, "files": file_sizes(output)}
        if not any(name.endswith(".safetensors") for name in manifest["files"]) or "config.json" not in manifest["files"]:
            raise DownloadError(f"{output} has no config.json or no safetensors after the download; the marker stays so it is not served")
        write_json(output / "download-manifest.json", manifest)
        (output / ".download-incomplete").unlink()
    return manifest


def verify(model_dir, monitor):
    """Raise unless ``model_dir`` is the finished download of ``monitor``'s model at its pinned revision, with every file the right size."""
    model_dir = Path(model_dir)
    path = model_dir / "download-manifest.json"
    if not path.is_file():
        raise DownloadError(f"{model_dir} has no download-manifest.json")
    if (model_dir / ".download-incomplete").exists():
        raise DownloadError(f"{model_dir}: the download was interrupted")
    manifest = read_json(path)
    if manifest["model_id"] != monitor.model_id:
        raise DownloadError(f"{model_dir} holds {manifest['model_id']}, the registry entry {monitor.name!r} is {monitor.model_id}")
    if monitor.revision != UNPINNED and manifest["revision"] != monitor.revision:
        raise DownloadError(f"{model_dir} is at {manifest['revision']}, the registry pins {monitor.revision}")
    for name, size in manifest["files"].items():
        target = model_dir / name
        if not target.is_file() or target.stat().st_size != size:
            raise DownloadError(f"{target} is missing or its size differs from the manifest")
    return manifest
