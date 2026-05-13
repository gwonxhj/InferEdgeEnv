from __future__ import annotations

import hashlib
import json
import posixpath
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from inferedge_env import __version__
from inferedge_env.result.schema import FAILED_RUN_SCHEMA_VERSION, RunResult
from inferedge_env.result.writer import SAMPLER_METADATA_REQUIRED_KEYS, load_result
from inferedge_env.samplers.base import SAMPLER_METADATA_SCHEMA_VERSION
from inferedge_env.utils.hashing import sha256_file


EXPORT_SCHEMA_VERSION = "edgeenv.export.v1"
EXPORT_BUNDLE_TYPE = "successful-run"
FAILED_EXPORT_BUNDLE_TYPE = "failed-run"
REQUIRED_RUN_FILES = [
    "result.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
]
REQUIRED_FAILED_RUN_FILES = [
    "failure.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
]
SAMPLER_METADATA_FILE = "sampler/metadata.json"


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


@dataclass(frozen=True)
class FailedRunImportPlan:
    archive_path: Path
    top_level: str
    failure: dict[str, Any]
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
    files.update(_collect_sampler_files(source_dir))
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


def export_failed_run(failed_dir: Path | str, output_path: Path | str) -> Path:
    source_dir = Path(failed_dir)
    destination = Path(output_path)
    failure = _load_failed_run_failure(source_dir)
    run_id = str(failure["run_id"])
    if source_dir.name != run_id:
        raise RunExportError(
            f"Failed run artifact directory name does not match run_id: {source_dir}"
        )

    files = _collect_required_files(source_dir, REQUIRED_FAILED_RUN_FILES)
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = _build_failed_manifest(failure, files)
    top_level = _safe_archive_dir(run_id)

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
            members = _bundle_members(infos, top_level)
            manifest = _read_manifest(archive, members["manifest.json"])
            _validate_manifest_header(manifest, EXPORT_BUNDLE_TYPE)
            file_entries = _manifest_file_entries(manifest)
            _verify_required_manifest_entries(file_entries, REQUIRED_RUN_FILES)
            _verify_archive_members_match_manifest(
                members,
                file_entries,
                REQUIRED_RUN_FILES,
            )
            _verify_manifest_checksums(
                archive,
                members,
                file_entries,
                REQUIRED_RUN_FILES,
            )
            _validate_sampler_extension(archive, members, file_entries)
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


def validate_failed_run_import(archive_path: Path | str) -> FailedRunImportPlan:
    source = Path(archive_path)
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            _reject_duplicate_archive_entries(infos)
            top_level = _single_top_level_dir(infos)
            members = _bundle_members(infos, top_level)
            manifest = _read_manifest(archive, members["manifest.json"])
            _validate_manifest_header(manifest, FAILED_EXPORT_BUNDLE_TYPE)
            file_entries = _manifest_file_entries(manifest)
            _verify_required_manifest_entries(file_entries, REQUIRED_FAILED_RUN_FILES)
            _verify_archive_members_match_manifest(
                members,
                file_entries,
                REQUIRED_FAILED_RUN_FILES,
            )
            _verify_manifest_checksums(
                archive,
                members,
                file_entries,
                REQUIRED_FAILED_RUN_FILES,
            )
            failure = _load_import_failure(archive, members["failure.json"])
            run_id = str(failure["run_id"])
            if manifest.get("run_id") != run_id:
                raise RunImportError("Manifest run_id does not match failure.json run_id")
            if top_level != run_id:
                raise RunImportError("Archive top-level directory does not match run_id")
            if manifest.get("source_failed_schema_version") != failure["schema_version"]:
                raise RunImportError(
                    "Manifest failed-run schema version does not match failure.json"
                )
            return FailedRunImportPlan(
                archive_path=source,
                top_level=top_level,
                failure=failure,
                members=members,
            )
    except zipfile.BadZipFile as exc:
        raise RunImportError(f"Invalid failed-run evidence zip: {source}") from exc


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
            for name in plan.members:
                if name == "manifest.json":
                    continue
                path = destination / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(plan.members[name]))
    except Exception:
        shutil.rmtree(destination)
        raise
    return plan.result, destination


def import_failed_run(
    archive_path: Path | str,
    edgeenv_root: Path | str = ".edgeenv",
) -> tuple[dict[str, Any], Path]:
    plan = validate_failed_run_import(archive_path)
    run_id = str(plan.failure["run_id"])
    destination = Path(edgeenv_root) / "failed-runs" / run_id
    if destination.exists():
        raise RunImportError(f"Failed-run artifact already exists: {destination}")
    destination.mkdir(parents=True)
    try:
        with zipfile.ZipFile(plan.archive_path) as archive:
            for name in REQUIRED_FAILED_RUN_FILES:
                (destination / name).write_bytes(archive.read(plan.members[name]))
    except Exception:
        for path in destination.iterdir():
            path.unlink()
        destination.rmdir()
        raise
    return plan.failure, destination


def _load_export_result(source_dir: Path) -> RunResult:
    result_path = source_dir / "result.json"
    try:
        return load_result(result_path)
    except (OSError, ValueError) as exc:
        raise RunExportError(f"Invalid successful run artifact: {source_dir}") from exc


def _load_failed_run_failure(source_dir: Path) -> dict[str, Any]:
    failure_path = source_dir / "failure.json"
    try:
        payload = json.loads(failure_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RunExportError(f"Invalid failed-run artifact: {source_dir}") from exc
    _validate_failure_payload(payload, error_cls=RunExportError)
    return payload


def _collect_required_files(
    source_dir: Path,
    required_files: list[str] = REQUIRED_RUN_FILES,
) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for name in required_files:
        path = source_dir / name
        if not path.is_file():
            raise RunExportError(f"Required run artifact file missing: {path}")
        files[name] = path
    return files


def _collect_sampler_files(source_dir: Path) -> dict[str, Path]:
    metadata_path = source_dir / SAMPLER_METADATA_FILE
    if not metadata_path.exists():
        return {}
    if not metadata_path.is_file():
        raise RunExportError(
            f"Sampler metadata artifact must be a file: {metadata_path}"
        )
    metadata = _load_sampler_metadata(metadata_path, RunExportError)
    raw_artifacts = _sampler_raw_artifact_paths(metadata, RunExportError)
    files = {SAMPLER_METADATA_FILE: metadata_path}
    for raw_artifact in raw_artifacts:
        raw_path = source_dir / Path(*PurePosixPath(raw_artifact).parts)
        if not raw_path.is_file():
            raise RunExportError(
                f"Sampler raw artifact listed in metadata is missing: {raw_artifact}"
            )
        if raw_path.is_symlink():
            raise RunExportError(
                f"Sampler raw artifact must not be a symlink: {raw_artifact}"
            )
        files[raw_artifact] = raw_path
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
                "required": name in REQUIRED_RUN_FILES,
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


def _build_failed_manifest(
    failure: dict[str, Any],
    files: dict[str, Path],
) -> dict[str, Any]:
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "bundle_type": FAILED_EXPORT_BUNDLE_TYPE,
        "run_id": failure["run_id"],
        "created_at": failure["created_at"],
        "source_failed_schema_version": failure["schema_version"],
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


def _bundle_members(
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
        raise RunImportError("Evidence manifest missing: manifest.json")
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


def _validate_manifest_header(manifest: dict[str, Any], bundle_type: str) -> None:
    if manifest.get("schema_version") != EXPORT_SCHEMA_VERSION:
        raise RunImportError("Unsupported run evidence export schema")
    if manifest.get("bundle_type") != bundle_type:
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
        try:
            _safe_archive_path("run", path)
        except RunExportError as exc:
            raise RunImportError(str(exc)) from exc
        if path in entries:
            raise RunImportError("Duplicate manifest file entries are not allowed")
        entries[path] = item
    return entries


def _verify_required_manifest_entries(
    entries: dict[str, dict[str, Any]],
    required_files: list[str],
) -> None:
    missing = [name for name in required_files if name not in entries]
    if missing:
        raise RunImportError(f"Required run artifact file missing: {', '.join(missing)}")


def _verify_archive_members_match_manifest(
    members: dict[str, zipfile.ZipInfo],
    entries: dict[str, dict[str, Any]],
    required_files: list[str],
) -> None:
    expected = set(entries) | {"manifest.json"}
    actual = set(members)
    if actual != expected:
        extra = sorted(actual - expected)
        missing = sorted(expected - actual)
        if extra:
            raise RunImportError(f"Unexpected archive file: {extra[0]}")
        if missing:
            raise RunImportError(f"Required run artifact file missing: {missing[0]}")
    for name in required_files:
        if entries[name].get("required") is not True:
            raise RunImportError(f"Manifest file entry is not marked required: {name}")
    unexpected_manifest_entries = [
        name for name in sorted(set(entries) - set(required_files))
        if not name.startswith("sampler/")
    ]
    if unexpected_manifest_entries:
        raise RunImportError(
            f"Unexpected manifest file entry: {unexpected_manifest_entries[0]}"
        )
    for name in sorted(set(entries) - set(required_files)):
        if entries[name].get("required") is not False:
            raise RunImportError(f"Optional manifest file entry is marked required: {name}")


def _verify_manifest_checksums(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    entries: dict[str, dict[str, Any]],
    required_files: list[str],
) -> None:
    for name in entries:
        entry = entries[name]
        data = archive.read(members[name])
        if entry.get("bytes") != len(data):
            raise RunImportError(f"Byte size mismatch for exported file: {name}")
        digest = hashlib.sha256(data).hexdigest()
        if entry.get("sha256") != digest:
            raise RunImportError(f"Checksum mismatch for exported file: {name}")


def _validate_sampler_extension(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
    entries: dict[str, dict[str, Any]],
) -> None:
    sampler_entries = {name for name in entries if name.startswith("sampler/")}
    if not sampler_entries:
        return
    if SAMPLER_METADATA_FILE not in sampler_entries:
        raise RunImportError("Sampler artifact metadata missing: sampler/metadata.json")
    metadata = _load_import_sampler_metadata(archive, members[SAMPLER_METADATA_FILE])
    raw_artifacts = set(_sampler_raw_artifact_paths(metadata, RunImportError))
    expected = raw_artifacts | {SAMPLER_METADATA_FILE}
    if sampler_entries != expected:
        extra = sorted(sampler_entries - expected)
        missing = sorted(expected - sampler_entries)
        if extra:
            raise RunImportError(f"Unexpected sampler artifact file: {extra[0]}")
        if missing:
            raise RunImportError(f"Sampler raw artifact missing: {missing[0]}")


def _load_import_sampler_metadata(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read(info))
    except json.JSONDecodeError as exc:
        raise RunImportError("Invalid sampler metadata JSON") from exc
    _validate_sampler_metadata(payload, RunImportError)
    return payload


def _load_sampler_metadata(
    path: Path,
    error_cls: type[RunImportError] | type[RunExportError],
) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise error_cls(f"Invalid sampler metadata artifact: {path}") from exc
    _validate_sampler_metadata(payload, error_cls)
    return payload


def _validate_sampler_metadata(
    payload: Any,
    error_cls: type[RunImportError] | type[RunExportError],
) -> None:
    if not isinstance(payload, dict):
        raise error_cls("sampler/metadata.json must be a JSON object")
    missing = sorted(SAMPLER_METADATA_REQUIRED_KEYS - payload.keys())
    if missing:
        raise error_cls(
            "Sampler metadata missing required keys: " + ", ".join(missing)
        )
    if payload.get("schema_version") != SAMPLER_METADATA_SCHEMA_VERSION:
        raise error_cls("Unsupported sampler metadata schema")
    if not isinstance(payload["raw_artifacts"], list):
        raise error_cls("Sampler metadata raw_artifacts must be a list")


def _sampler_raw_artifact_paths(
    metadata: dict[str, Any],
    error_cls: type[RunImportError] | type[RunExportError],
) -> list[str]:
    paths: list[str] = []
    for item in metadata["raw_artifacts"]:
        if not isinstance(item, str):
            raise error_cls("Sampler metadata raw_artifacts entries must be strings")
        path = PurePosixPath(item)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise error_cls(f"Unsafe sampler raw artifact path: {item}")
        if not path.parts or path.parts[0] != "sampler":
            raise error_cls(f"Sampler raw artifact must be under sampler/: {item}")
        if item == SAMPLER_METADATA_FILE:
            raise error_cls(
                "Sampler metadata cannot list metadata.json as a raw artifact"
            )
        paths.append(path.as_posix())
    if len(paths) != len(set(paths)):
        raise error_cls("Duplicate sampler raw artifacts are not allowed")
    return paths


def _load_import_result(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> RunResult:
    try:
        return RunResult.model_validate_json(archive.read(info))
    except ValueError as exc:
        raise RunImportError("Invalid result.json in run evidence bundle") from exc


def _load_import_failure(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> dict[str, Any]:
    try:
        payload = json.loads(archive.read(info))
    except json.JSONDecodeError as exc:
        raise RunImportError("Invalid failure.json in failed-run evidence bundle") from exc
    _validate_failure_payload(payload)
    return payload


def _validate_failure_payload(
    payload: Any,
    error_cls: type[RunImportError] | type[RunExportError] = RunImportError,
) -> None:
    if not isinstance(payload, dict):
        raise error_cls("failure.json must be a JSON object")
    if payload.get("schema_version") != FAILED_RUN_SCHEMA_VERSION:
        raise error_cls("Unsupported failed-run schema")
    run_id = payload.get("run_id")
    if not isinstance(run_id, str):
        raise error_cls("failure.json run_id must be a string")
    try:
        _safe_archive_dir(run_id)
    except RunExportError as exc:
        raise error_cls(str(exc)) from exc
    if "created_at" not in payload:
        raise error_cls("failure.json missing created_at")
