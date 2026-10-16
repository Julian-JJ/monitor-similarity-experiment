"""Bind the server's API model name to its recorded launch configuration."""

from .artifacts import digest


def make_manifest(settings):
    name = f"{settings['model_id']}@{digest(settings)}"
    return {"schema_version": 2, "settings": settings, "served_model_name": name,
            "command": [*settings["command"], "--served-model-name", name]}


def validate_manifest(manifest, download_manifest):
    if manifest.get("schema_version") != 2:
        raise ValueError("Restart with serve_model.py to create a version-2 serving manifest")
    settings = manifest["settings"]
    if manifest != make_manifest(settings):
        raise ValueError("Serving manifest settings, command, and model name disagree")
    if (settings["model_id"], settings["revision"], settings["download_manifest_hash"]) != (
            download_manifest["model_id"], download_manifest["revision"], digest(download_manifest)):
        raise ValueError("Serving manifest and downloaded model manifest disagree")
    return manifest["served_model_name"]
