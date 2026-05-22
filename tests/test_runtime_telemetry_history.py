from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from helpers import make_result
from inferedge_env.cli import app
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.telemetry_history import (
    RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
    RuntimeTelemetryHistoryError,
    build_runtime_telemetry_history,
    write_runtime_telemetry_history,
)
from inferedge_env.result.writer import ResultArtifactWriter
from inferedge_env.runners.fake import FakeRunner


def test_build_runtime_telemetry_history_records_entries_and_missing_gaps(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-without-telemetry",
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-with-telemetry",
        runtime_telemetry=_runtime_telemetry_payload(),
    )

    payload = build_runtime_telemetry_history(
        edgeenv_root,
        generated_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
    )

    assert payload["schema_version"] == RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION
    assert payload["generated_at"] == "2026-05-22T00:00:00+00:00"
    assert payload["summary"] == {
        "requested_runs": None,
        "registered_runs": 2,
        "telemetry_runs": 1,
        "missing_telemetry_runs": 1,
    }
    assert payload["runs"][0]["run_id"] == "run-with-telemetry"
    assert payload["runs"][0]["telemetry_timestamp"] == "2026-05-22T00:00:00Z"
    assert payload["runs"][0]["execution_sequence_id"] == 7
    assert payload["runs"][0]["runtime_telemetry"]["resource"] == {
        "telemetry_source": "runtime-result"
    }
    assert payload["runs"][0]["protocol"]["repeat_runs"] == 10
    assert payload["missing_telemetry"] == [
        {
            "run_id": "run-without-telemetry",
            "reason": "runtime_telemetry_missing",
        }
    ]
    assert "not production monitoring" in payload["notes"][0]


def test_write_runtime_telemetry_history_filters_selected_runs(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-a",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=1),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-b",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=2),
    )
    output_path = tmp_path / "history" / "runtime-telemetry-history.json"

    payload = write_runtime_telemetry_history(
        edgeenv_root,
        output_path,
        run_ids=["run-b", "run-b"],
    )

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == payload
    assert payload["summary"]["requested_runs"] == 2
    assert payload["summary"]["registered_runs"] == 1
    assert payload["summary"]["telemetry_runs"] == 1
    assert payload["runs"][0]["run_id"] == "run-b"
    assert payload["runs"][0]["execution_sequence_id"] == 2


def test_build_runtime_telemetry_history_rejects_unknown_selected_run(tmp_path):
    with pytest.raises(RuntimeTelemetryHistoryError, match="Run not found: missing-run"):
        build_runtime_telemetry_history(
            tmp_path / ".edgeenv",
            run_ids=["missing-run"],
        )


def test_cli_runs_telemetry_export_history_writes_replay_artifact(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-cli-telemetry",
        runtime_telemetry=_runtime_telemetry_payload(),
    )
    output_path = tmp_path / "runtime-telemetry-history.json"

    result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "export-history",
            "--output",
            str(output_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0
    assert "Runtime telemetry history exported" in result.output
    assert "Telemetry entries: 1" in result.output
    assert "not production monitoring" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["telemetry_runs"] == 1
    assert payload["runs"][0]["run_id"] == "run-cli-telemetry"


def _write_registered_run(
    edgeenv_root,
    bench_config,
    target_profile,
    config_files,
    *,
    run_id: str,
    runtime_telemetry: dict | None = None,
):
    bench_path, profile_path = config_files
    runner_result = FakeRunner().run(bench_config, target_profile).model_copy(
        update={"runtime_telemetry": runtime_telemetry}
    )
    result = make_result(
        bench_config,
        target_profile,
        run_id=run_id,
        runner_result=runner_result,
    )
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result,
        bench_path,
        profile_path,
        runner_result.stdout,
        runner_result.stderr,
    )
    RunRegistry(edgeenv_root / "runs.db").insert(result, run_dir / "result.json")
    return run_dir


def _runtime_telemetry_payload(sequence_id: int = 7) -> dict:
    return {
        "schema_version": "inferedge-runtime-telemetry-v1",
        "collection_mode": "single_result_export",
        "telemetry_timestamp": "2026-05-22T00:00:00Z",
        "execution_sequence_id": sequence_id,
        "latency": {
            "mean_ms": 10.0,
            "p99_ms": 12.0,
        },
        "resource": {
            "telemetry_source": "runtime-result",
        },
        "operation": {
            "timeout_observed": False,
        },
        "missing_fields": ["queue_depth"],
        "production_monitoring": False,
    }
