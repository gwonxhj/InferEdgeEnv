from __future__ import annotations

import json
import zipfile

import pytest

from inferedge_env.result.exporter import (
    REQUIRED_FAILED_RUN_FILES,
    REQUIRED_RUN_FILES,
    RunExportError,
    RunImportError,
    _safe_archive_path,
    export_failed_run,
    export_successful_run,
    import_failed_run,
    import_successful_run,
)
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.result.writer import FailedRunArtifactWriter, ResultArtifactWriter, load_result
from inferedge_env.utils.hashing import sha256_file
from inferedge_env.runners.fake import FakeRunner
from helpers import make_result


def test_result_json_files_created(tmp_path, bench_config, target_profile, config_files):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile)
    result = make_result(bench_config, target_profile, run_id="run-artifact")

    run_dir = ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )

    assert (run_dir / "result.json").is_file()
    assert (run_dir / "config.yaml").is_file()
    assert (run_dir / "target.yaml").is_file()
    assert (run_dir / "env.json").is_file()
    assert (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert (run_dir / "stderr.log").read_text(encoding="utf-8") == ""
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-artifact"
    assert payload["schema_version"] == "edgeenv.result.v1"
    assert "resource_metrics" not in payload
    loaded = load_result(run_dir / "result.json")
    assert loaded.resource_metrics is None


def test_result_json_persists_resource_metrics(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile).model_copy(
        update={
            "resource_metrics": ResourceMetrics(
                memory_peak_mb=512.0,
                power_mean_w=8.2,
                source="benchmark-command",
            )
        }
    )
    result = make_result(
        bench_config,
        target_profile,
        run_id="run-resource",
        runner_result=runner_result,
    )

    run_dir = ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )

    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["resource_metrics"]["memory_peak_mb"] == 512.0
    assert payload["resource_metrics"]["power_mean_w"] == 8.2
    assert payload["resource_metrics"]["source"] == "benchmark-command"


def test_failed_run_artifact_files_created(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    bench_path, profile_path = config_files

    failed_dir = FailedRunArtifactWriter(tmp_path / ".edgeenv").write(
        config=bench_config,
        target=target_profile,
        config_path=bench_path,
        target_path=profile_path,
        error_message="Local benchmark command failed with exit code 7",
        stdout="failed stdout\n",
        stderr="failed stderr\n",
        return_code=7,
        run_id="run-failed",
        env={"python_version": "test"},
    )

    assert (failed_dir / "failure.json").is_file()
    assert (failed_dir / "config.yaml").is_file()
    assert (failed_dir / "target.yaml").is_file()
    assert (failed_dir / "env.json").is_file()
    assert (failed_dir / "stdout.log").read_text(encoding="utf-8") == "failed stdout\n"
    assert (failed_dir / "stderr.log").read_text(encoding="utf-8") == "failed stderr\n"
    payload = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "edgeenv.failed-run.v1"
    assert payload["run_id"] == "run-failed"
    assert payload["return_code"] == 7
    assert payload["error_type"] == "LocalRunnerError"


def test_export_successful_run_creates_manifest_and_checksums(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile)
    result = make_result(bench_config, target_profile, run_id="run-export")
    run_dir = ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )
    output_path = tmp_path / "exports" / "edgeenv-run-export.zip"

    archive_path = export_successful_run(run_dir, output_path)

    assert archive_path == output_path
    assert archive_path.is_file()
    with zipfile.ZipFile(archive_path) as archive:
        names = sorted(archive.namelist())
        assert names == sorted(
            [f"run-export/{name}" for name in [*REQUIRED_RUN_FILES, "manifest.json"]]
        )
        manifest = json.loads(archive.read("run-export/manifest.json"))
        assert manifest["schema_version"] == "edgeenv.export.v1"
        assert manifest["bundle_type"] == "successful-run"
        assert manifest["run_id"] == "run-export"
        assert manifest["source_result_schema_version"] == "edgeenv.result.v1"
        assert manifest["exported_by"]["tool"] == "edgeenv"
        file_entries = {entry["path"]: entry for entry in manifest["files"]}
        assert sorted(file_entries) == sorted(REQUIRED_RUN_FILES)
        for name in REQUIRED_RUN_FILES:
            entry = file_entries[name]
            data = archive.read(f"run-export/{name}")
            assert entry["required"] is True
            assert entry["bytes"] == len(data)
            assert entry["sha256"] == sha256_file(run_dir / name)


def test_export_successful_run_rejects_missing_required_file(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile)
    result = make_result(bench_config, target_profile, run_id="run-export-missing")
    run_dir = ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )
    (run_dir / "stdout.log").unlink()

    with pytest.raises(RunExportError, match="Required run artifact file missing"):
        export_successful_run(run_dir, tmp_path / "missing.zip")


def test_export_archive_path_safety_rejects_traversal():
    assert _safe_archive_path("run-safe", "result.json") == "run-safe/result.json"
    with pytest.raises(RunExportError, match="Unsafe export archive path"):
        _safe_archive_path("run-safe", "../result.json")
    with pytest.raises(RunExportError, match="Unsafe export archive path component"):
        _safe_archive_path("../run-safe", "result.json")


def test_import_successful_run_copies_files_after_validation(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    run_dir = _write_export_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-import",
    )
    archive_path = export_successful_run(run_dir, tmp_path / "run-import.zip")
    result, imported_dir = import_successful_run(
        archive_path,
        tmp_path / "imported-edgeenv",
    )

    assert result.run_id == "run-import"
    assert imported_dir == tmp_path / "imported-edgeenv" / "runs" / "run-import"
    for name in REQUIRED_RUN_FILES:
        assert (imported_dir / name).read_bytes() == (run_dir / name).read_bytes()
    assert not (imported_dir / "manifest.json").exists()


def test_import_successful_run_rejects_checksum_mismatch(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    run_dir = _write_export_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-import-checksum",
    )
    archive_path = export_successful_run(run_dir, tmp_path / "run-import-checksum.zip")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(tampered, "w") as dest:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "run-import-checksum/stdout.log":
                data = b"x" + data[1:]
            dest.writestr(info, data)

    with pytest.raises(RunImportError, match="Checksum mismatch"):
        import_successful_run(tampered, tmp_path / "imported-edgeenv")
    assert not (tmp_path / "imported-edgeenv").exists()


def test_import_successful_run_rejects_unsafe_archive_path(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    run_dir = _write_export_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-import-unsafe",
    )
    archive_path = export_successful_run(run_dir, tmp_path / "run-import-unsafe.zip")
    unsafe = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(unsafe, "w") as dest:
        for info in source.infolist():
            dest.writestr(info, source.read(info))
        dest.writestr("../outside.txt", "nope")

    with pytest.raises(RunImportError, match="Unsafe archive entry path"):
        import_successful_run(unsafe, tmp_path / "imported-edgeenv")


def test_import_successful_run_rejects_existing_run_directory(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    run_dir = _write_export_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-import-existing",
    )
    archive_path = export_successful_run(run_dir, tmp_path / "run-import-existing.zip")
    destination_root = tmp_path / "imported-edgeenv"
    (destination_root / "runs" / "run-import-existing").mkdir(parents=True)

    with pytest.raises(RunImportError, match="Run artifact already exists"):
        import_successful_run(archive_path, destination_root)


def test_export_failed_run_creates_manifest_and_checksums(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    failed_dir = _write_failed_run_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-failed-export",
    )
    archive_path = export_failed_run(
        failed_dir,
        tmp_path / "edgeenv-failed-run-export.zip",
    )

    with zipfile.ZipFile(archive_path) as archive:
        names = sorted(archive.namelist())
        assert names == sorted(
            [
                f"run-failed-export/{name}"
                for name in [*REQUIRED_FAILED_RUN_FILES, "manifest.json"]
            ]
        )
        manifest = json.loads(archive.read("run-failed-export/manifest.json"))
        assert manifest["schema_version"] == "edgeenv.export.v1"
        assert manifest["bundle_type"] == "failed-run"
        assert manifest["run_id"] == "run-failed-export"
        assert manifest["source_failed_schema_version"] == "edgeenv.failed-run.v1"
        file_entries = {entry["path"]: entry for entry in manifest["files"]}
        assert sorted(file_entries) == sorted(REQUIRED_FAILED_RUN_FILES)
        for name in REQUIRED_FAILED_RUN_FILES:
            assert file_entries[name]["sha256"] == sha256_file(failed_dir / name)


def test_import_failed_run_copies_files_without_registry(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    failed_dir = _write_failed_run_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-failed-import",
    )
    archive_path = export_failed_run(failed_dir, tmp_path / "failed.zip")
    failure, imported_dir = import_failed_run(
        archive_path,
        tmp_path / "imported-edgeenv",
    )

    assert failure["run_id"] == "run-failed-import"
    assert imported_dir == (
        tmp_path / "imported-edgeenv" / "failed-runs" / "run-failed-import"
    )
    for name in REQUIRED_FAILED_RUN_FILES:
        assert (imported_dir / name).read_bytes() == (failed_dir / name).read_bytes()
    assert not (tmp_path / "imported-edgeenv" / "runs.db").exists()
    assert not (imported_dir / "manifest.json").exists()


def test_import_failed_run_rejects_checksum_mismatch(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    failed_dir = _write_failed_run_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-failed-checksum",
    )
    archive_path = export_failed_run(failed_dir, tmp_path / "failed-checksum.zip")
    tampered = tmp_path / "failed-tampered.zip"
    with zipfile.ZipFile(archive_path) as source, zipfile.ZipFile(tampered, "w") as dest:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "run-failed-checksum/stderr.log":
                data = b"x" + data[1:]
            dest.writestr(info, data)

    with pytest.raises(RunImportError, match="Checksum mismatch"):
        import_failed_run(tampered, tmp_path / "imported-edgeenv")
    assert not (tmp_path / "imported-edgeenv").exists()


def test_import_failed_run_rejects_successful_run_bundle(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    run_dir = _write_export_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-success-not-failed",
    )
    archive_path = export_successful_run(run_dir, tmp_path / "successful.zip")

    with pytest.raises(RunImportError, match="Unsupported run evidence bundle type"):
        import_failed_run(archive_path, tmp_path / "imported-edgeenv")


def test_import_failed_run_rejects_existing_failed_run_directory(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    failed_dir = _write_failed_run_fixture(
        tmp_path,
        bench_config,
        target_profile,
        config_files,
        run_id="run-failed-existing",
    )
    archive_path = export_failed_run(failed_dir, tmp_path / "failed-existing.zip")
    destination_root = tmp_path / "imported-edgeenv"
    (destination_root / "failed-runs" / "run-failed-existing").mkdir(parents=True)

    with pytest.raises(RunImportError, match="Failed-run artifact already exists"):
        import_failed_run(archive_path, destination_root)


def _write_export_fixture(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
    run_id: str,
):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile)
    result = make_result(bench_config, target_profile, run_id=run_id)
    return ResultArtifactWriter(tmp_path / ".edgeenv").write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )


def _write_failed_run_fixture(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
    run_id: str,
):
    bench_path, profile_path = config_files
    return FailedRunArtifactWriter(tmp_path / ".edgeenv").write(
        config=bench_config,
        target=target_profile,
        config_path=bench_path,
        target_path=profile_path,
        error_message="Local benchmark command failed with exit code 7",
        stdout="failed stdout\n",
        stderr="failed stderr\n",
        return_code=7,
        run_id=run_id,
        env={"python_version": "test"},
    )
