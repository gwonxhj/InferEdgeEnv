from __future__ import annotations

import json
import posixpath
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from inferedge_env import __version__
from inferedge_env.result.schema import RunResult
from inferedge_env.result.writer import load_result
from inferedge_env.utils.hashing import sha256_file


EXPORT_SCHEMA_VERSION = "edgeenv.export.v1"
EXPORT_BUNDLE_TYPE = "successful-run"
REQUIRED_RUN_FILES = [
    "result.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
]


class RunExportError(ValueError):
    """Raised when a successful run artifact cannot be exported safely."""


def export_successful_run(run_dir: Path | str, output_path: Path | str) -> Path:
    source_dir = Path(run_dir)
    destination = Path(output_path)
    result = _load_export_result(source_dir)
    if source_dir.name != result.run_id:
        raise RunExportError(
            f"Run artifact directory name does not match result run_id: {source_dir}"
        )

    files = _collect_required_files(source_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = _build_manifest(result, files)
    top_level = _safe_archive_dir(result.run_id)

    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            _safe_archive_path(top_level, "manifest.json"),
            json.dumps(manifest, indent=2, sort_keys=True),
        )
        for name, path in files.items():
            archive.write(path, _safe_archive_path(top_level, name))
    return destination


def _load_export_result(source_dir: Path) -> RunResult:
    result_path = source_dir / "result.json"
    try:
        return load_result(result_path)
    except (OSError, ValueError) as exc:
        raise RunExportError(f"Invalid successful run artifact: {source_dir}") from exc


def _collect_required_files(source_dir: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for name in REQUIRED_RUN_FILES:
        path = source_dir / name
        if not path.is_file():
            raise RunExportError(f"Required run artifact file missing: {path}")
        files[name] = path
    return files


def _build_manifest(result: RunResult, files: dict[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "bundle_type": EXPORT_BUNDLE_TYPE,
        "run_id": result.run_id,
        "created_at": result.created_at.isoformat(),
        "source_result_schema_version": result.schema_version,
        "files": [
            {
                "path": name,
                "required": True,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for name, path in files.items()
        ],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "exported_by": {
            "tool": "edgeenv",
            "package": "inferedge_env",
            "version": __version__,
        },
    }


def _safe_archive_dir(run_id: str) -> str:
    return _safe_archive_component(run_id)


def _safe_archive_path(top_level: str, relative_path: str) -> str:
    safe_top = _safe_archive_component(top_level)
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RunExportError(f"Unsafe export archive path: {relative_path}")
    archive_path = posixpath.join(safe_top, relative.as_posix())
    if archive_path.startswith("/") or "/../" in f"/{archive_path}/":
        raise RunExportError(f"Unsafe export archive path: {relative_path}")
    return archive_path


def _safe_archive_component(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or len(path.parts) != 1 or value in {".", ".."}:
        raise RunExportError(f"Unsafe export archive path component: {value}")
    if "\\" in value:
        raise RunExportError(f"Unsafe export archive path component: {value}")
    return value
