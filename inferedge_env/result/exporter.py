from __future__ import annotations

import json
import posixpath
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
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


class RunImportError(ValueError):
    """Raised when a run evidence bundle cannot be imported safely."""


@dataclass(frozen=True)
class RunImportPlan:
    archive_path: Path
    top_level: str
    result: RunResult
    members: dict[str, zipfile.ZipInfo]


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


def validate_successful_run_import(archive_path: Path | str) -> RunImportPlan:
    source = Path(archive_path)
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            _reject_duplicate_archive_entries(infos)
            top_level = _single_top_level_dir(infos)
            members = _successful_run_members(archive, infos, top_level)
            manifest = _read_manifest(archive, members["manifest.json"])
            _validate_manifest_header(manifest)
            file_entries = _manifest_file_entries(manifest)
            _verify_required_manifest_entries(file_entries)
            _verify_archive_members_match_manifest(members, file_entries)
            _verify_manifest_checksums(archive, members, file_entries)
            result = _load_import_result(archive, members["result.json"])
            if manifest.get("run_id") != result.run_id:
                raise RunImportError("Manifest run_id does not match result.json run_id")
            if top_level != result.run_id:
                raise RunImportError("Archive top-level directory does not match run_id")
            if manifest.get("source_result_schema_version") != result.schema_version:
                raise RunImportError(
                    "Manifest result schema version does not match result.json"
                )
            return RunImportPlan(
                archive_path=source,
                top_level=top_level,
                result=result,
                members=members,
            )
    except zipfile.BadZipFile as exc:
        raise RunImportError(f"Invalid run evidence zip: {source}") from exc


def import_successful_run(
    archive_path: Path | str,
    edgeenv_root: Path | str = ".edgeenv",
) -> tuple[RunResult, Path]:
    plan = validate_successful_run_import(archive_path)
    destination = Path(edgeenv_root) / "runs" / plan.result.run_id
    if destination.exists():
        raise RunImportError(f"Run artifact already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(plan.archive_path) as archive:
            for name in REQUIRED_RUN_FILES:
                (destination / name).write_bytes(archive.read(plan.members[name]))
    except Exception:
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise
    return plan.result, destination


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


def _reject_duplicate_archive_entries(infos: list[zipfile.ZipInfo]) -> None:
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise RunImportError("Duplicate archive entries are not allowed")


def _single_top_level_dir(infos: list[zipfile.ZipInfo]) -> str:
    top_levels: set[str] = set()
    for info in infos:
        parts = _safe_member_parts(info)
        if len(parts) < 2:
            raise RunImportError("Archive entries must be under a run_id directory")
        top_levels.add(parts[0])
    if len(top_levels) != 1:
        raise RunImportError("Archive must contain exactly one top-level run directory")
    return next(iter(top_levels))


def _successful_run_members(
    archive: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
    top_level: str,
) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        parts = _safe_member_parts(info)
        if parts[0] != top_level:
            raise RunImportError("Archive member is outside the run directory")
        relative_path = "/".join(parts[1:])
        if relative_path in members:
            raise RunImportError("Duplicate archive entries are not allowed")
        if _is_zipinfo_symlink(info) or info.is_dir():
            raise RunImportError("Archive symlinks and directories are not importable")
        members[relative_path] = info
    if "manifest.json" not in members:
        raise RunImportError("Run evidence manifest missing: manifest.json")
    return members


def _safe_member_parts(info: zipfile.ZipInfo) -> tuple[str, ...]:
    filename = info.filename
    if filename.startswith("/") or "\\" in filename:
        raise RunImportError(f"Unsafe archive entry path: {filename}")
    path = PurePosixPath(filename)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RunImportError(f"Unsafe archive entry path: {filename}")
    return path.parts


def _is_zipinfo_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _read_manifest(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read(info))
    except json.JSONDecodeError as exc:
        raise RunImportError("Invalid run evidence manifest JSON") from exc
    if not isinstance(payload, dict):
        raise RunImportError("Run evidence manifest must be a JSON object")
    return payload


def _validate_manifest_header(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise RunImportError("Unsupported run evidence export schema")
    if manifest.get("bundle_type") != EXPORT_BUNDLE_TYPE:
        raise RunImportError("Unsupported run evidence bundle type")


def _manifest_file_entries(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_files = manifest.get("files")
    if not isinstance(raw_files, list):
        raise RunImportError("Run evidence manifest files must be a list")
    entries: dict[str, dict[str, Any]] = {}
    for item in raw_files:
        if not isinstance(item, dict):
            raise RunImportError("Run evidence manifest file entries must be objects")
        path = item.get("path")
        if not isinstance(path, str):
            raise RunImportError("Run evidence manifest file path must be a string")
        _safe_archive_path("run", path)
        if path in entries:
            raise RunImportError("Duplicate manifest file entries are not allowed")
        entries[path] = item
    return entries


def _verify_required_manifest_entries(entries: dict[str, dict[str, Any]]) -> None:
    missing = [name for name in REQUIRED_RUN_FILES if name not in entries]
    if missing:
        raise RunImportError(f"Required run artifact file missing: {', '.join(missing)}")


def _verify_archive_members_match_manifest(
    members: dict[str, zipfile.ZipInfo],
    entries: dict[str, dict[str, Any]],
) -> None:
    expected = set(REQUIRED_RUN_FILES) | {"manifest.json"}
    actual = set(members)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        if extra:
            raise RunImportError(f"Unexpected archive file: {extra[0]}")
        if missing:
            raise RunImportError(f"Required run artifact file missing: {missing[0]}")
    for name in REQUIRED_RUN_FILES:
        if entries[name].get("required") is not True:
            raise RunImportError(f"Manifest file entry is not marked required: {name}")
    unexpected_manifest_entries = sorted(set(entries) - set(REQUIRED_RUN_FILES))
    if unexpected_manifest_entries:
        raise RunImportError(
            f"Unexpected manifest file entry: {unexpected_manifest_entries[0]}"
        )


def _verify_manifest_checksums(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    entries: dict[str, dict[str, Any]],
) -> None:
    for name in REQUIRED_RUN_FILES:
        entry = entries[name]
        data = archive.read(members[name])
        if entry.get("bytes") != len(data):
            raise RunImportError(f"Byte size mismatch for exported file: {name}")
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != digest:
            raise RunImportError(f"Checksum mismatch for exported file: {name}")


def _load_import_result(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> RunResult:
    try:
        return RunResult.model_validate_json(archive.read(info))
    except ValueError as exc:
        raise RunImportError("Invalid result.json in run evidence bundle") from exc
