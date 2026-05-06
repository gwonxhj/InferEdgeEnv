from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path | str) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_model_hash(model_path: Path | str) -> str:
    source = Path(model_path)
    if source.is_file():
        return sha256_file(source)
    marker = f"missing-model-path:{source.as_posix()}"
    return hashlib.sha256(marker.encode("utf-8")).hexdigest()
