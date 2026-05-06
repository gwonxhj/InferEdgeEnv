from __future__ import annotations

from pathlib import Path


def default_edgeenv_root() -> Path:
    return Path(".edgeenv")


def default_registry_path(root: Path | str = ".edgeenv") -> Path:
    return Path(root) / "runs.db"


def result_json_path(root: Path | str, run_id: str) -> Path:
    return Path(root) / "runs" / run_id / "result.json"
