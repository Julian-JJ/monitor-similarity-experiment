"""Download a pinned upstream release and record file hashes on cluster storage."""
import hashlib
import json
from pathlib import Path
import sys

from huggingface_hub import HfApi, snapshot_download

REPO = "fastino/GLiDE-9B"
REVISION = "ab54df5acba0eebf7df45560ffdaacd64e32df3b"
REQUIREMENTS_SHA256 = "16b3db96b1fc595622f259a3d41ab50962a940aa561396096d02bfec4745c064"


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    project = Path(sys.argv[1]).resolve()
    target = project / "models/glide-9b-ab54df5a"
    info = HfApi().model_info(REPO, revision=REVISION, files_metadata=True)
    if info.sha != REVISION:
        raise RuntimeError("Unexpected model revision")
    snapshot_download(REPO, revision=REVISION, local_dir=target, max_workers=4)
    files = []
    for item in info.siblings:
        path = target / item.rfilename
        size = path.stat().st_size
        if item.size is not None and size != item.size:
            raise RuntimeError(f"Size mismatch: {item.rfilename}")
        digest = sha256(path)
        if item.lfs is not None and digest != item.lfs.sha256:
            raise RuntimeError(f"Upstream SHA256 mismatch: {item.rfilename}")
        files.append({"path": item.rfilename, "size": size, "sha256": digest})
    if sha256(target / "requirements.txt") != REQUIREMENTS_SHA256:
        raise RuntimeError("Unexpected installation requirements")
    record = {"repo": REPO, "revision": REVISION, "files": files,
              "gpu_inference_verified": False}
    (target / "download-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Verified {len(files)} downloaded files in {target}")


if __name__ == "__main__":
    main()
