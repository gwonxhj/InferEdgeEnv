from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from helpers import make_result
from inferedge_env.cli import app
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
    RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
    RuntimeTelemetryHistoryError,
    build_runtime_telemetry_history,
    inspect_runtime_telemetry_history,
    load_runtime_telemetry_history,
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
        "orchestrator_feed_runs": 0,
    }
    assert payload["runs"][0]["run_id"] == "run-with-telemetry"
    assert payload["runs"][0]["telemetry_timestamp"] == "2026-05-22T00:00:00Z"
    assert payload["runs"][0]["execution_sequence_id"] == 7
    assert payload["runs"][0]["runtime_telemetry"]["resource"] == {
        "telemetry_source": "runtime-result"
    }
    assert payload["runs"][0]["runtime_telemetry"]["coverage"] == {
        "schema_version": "inferedge-runtime-telemetry-coverage-v1",
        "expected_fields": ["queue_depth", "gpu_temperature"],
        "observed_fields": ["gpu_temperature"],
        "missing_fields": ["queue_depth"],
        "expected_field_count": 2,
        "observed_field_count": 1,
        "missing_field_count": 1,
        "coverage_ratio": 0.5,
        "comparability_owner": "edgeenv",
        "missing_telemetry_is_failure": False,
    }
    assert payload["telemetry_coverage"]["missing_field_runs"] == [
        {
            "run_id": "run-with-telemetry",
            "missing_fields": ["queue_depth"],
            "missing_field_count": 1,
            "missing_telemetry_is_failure": False,
        }
    ]
    assert payload["telemetry_coverage"]["run_summaries"] == [
        {
            "run_id": "run-with-telemetry",
            "coverage_present": True,
            "expected_fields": ["gpu_temperature", "queue_depth"],
            "observed_fields": ["gpu_temperature"],
            "missing_fields": ["queue_depth"],
            "expected_field_count": 2,
            "observed_field_count": 1,
            "missing_field_count": 1,
            "coverage_ratio": 0.5,
            "missing_telemetry_is_failure": False,
        }
    ]
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


def test_build_runtime_telemetry_history_attaches_orchestrator_feed_context(
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
        run_id="candidate",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=2),
    )
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(
        json.dumps(_orchestrator_feed_payload("candidate")),
        encoding="utf-8",
    )

    payload = build_runtime_telemetry_history(
        edgeenv_root,
        generated_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
        orchestrator_feeds=[feed_path],
    )

    assert payload["summary"]["orchestrator_feed_runs"] == 1
    context = payload["runs"][0]["orchestrator_operation_context"]
    assert context["schema_version"] == ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION
    assert context["not_a_regression_judgement"] is True
    assert context["not_a_comparability_gate"] is True
    assert context["decision_owner"] == "lab"
    assert context["regression_owner"] == "edgeenv"
    assert context["candidate_context"]["operation"]["queue_depth"] == 7
    assert context["candidate_context"]["resource"]["gpu_temperature"] == 78.5
    assert "not a regression judgement" in payload["notes"][3]


def test_build_runtime_telemetry_history_rejects_feed_for_unselected_run(
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
        run_id="candidate",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=2),
    )
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(
        json.dumps(_orchestrator_feed_payload("other-run")),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="Orchestrator telemetry feed run is not selected",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_cli_runs_telemetry_export_history_attaches_orchestrator_feed(
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
        run_id="candidate",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=2),
    )
    output_path = tmp_path / "runtime-telemetry-history.json"
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(
        json.dumps(_orchestrator_feed_payload("candidate")),
        encoding="utf-8",
    )

    export_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "export-history",
            "--output",
            str(output_path),
            "--edgeenv-root",
            str(edgeenv_root),
            "--orchestrator-feed",
            str(feed_path),
        ],
    )
    inspect_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "inspect-history",
            str(output_path),
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    assert "Orchestrator context entries: 1" in export_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Orchestrator context runs: 1" in inspect_result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["runs"][0]["orchestrator_operation_context"]["run_id"] == (
        "candidate"
    )


def test_inspect_runtime_telemetry_history_reports_replay_summary(
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
    payload = build_runtime_telemetry_history(edgeenv_root)

    summary = inspect_runtime_telemetry_history(payload)

    assert summary["valid"] is True
    assert summary["schema_version"] == RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION
    assert summary["replay"]["run_ids"] == ["run-a", "run-b"]
    assert summary["replay"]["execution_sequence_ids"] == [1, 2]
    assert summary["replay"]["sequence_monotonic"] is True
    assert summary["replay"]["evidence_gap_count"] == 1
    assert summary["replay"]["missing_run_ids"] == ["run-without-telemetry"]
    assert "latency" in summary["replay"]["telemetry_fields"]
    assert "operation" in summary["replay"]["telemetry_fields"]
    assert summary["replay"]["telemetry_coverage"] == {
        "runs_with_coverage": 2,
        "runs_without_coverage": 0,
        "expected_fields": ["gpu_temperature", "queue_depth"],
        "observed_fields": ["gpu_temperature"],
        "missing_fields": ["queue_depth"],
        "coverage_ratio_min": 0.5,
        "coverage_ratio_max": 0.5,
        "missing_telemetry_is_failure_values": [False],
        "any_missing_telemetry_is_failure": False,
        "missing_field_run_count": 2,
        "missing_field_runs": [
            {
                "run_id": "run-a",
                "missing_fields": ["queue_depth"],
                "missing_field_count": 1,
                "missing_telemetry_is_failure": False,
            },
            {
                "run_id": "run-b",
                "missing_fields": ["queue_depth"],
                "missing_field_count": 1,
                "missing_telemetry_is_failure": False,
            },
        ],
        "run_summaries": [
            {
                "run_id": "run-a",
                "coverage_present": True,
                "expected_fields": ["gpu_temperature", "queue_depth"],
                "observed_fields": ["gpu_temperature"],
                "missing_fields": ["queue_depth"],
                "expected_field_count": 2,
                "observed_field_count": 1,
                "missing_field_count": 1,
                "coverage_ratio": 0.5,
                "missing_telemetry_is_failure": False,
            },
            {
                "run_id": "run-b",
                "coverage_present": True,
                "expected_fields": ["gpu_temperature", "queue_depth"],
                "observed_fields": ["gpu_temperature"],
                "missing_fields": ["queue_depth"],
                "expected_field_count": 2,
                "observed_field_count": 1,
                "missing_field_count": 1,
                "coverage_ratio": 0.5,
                "missing_telemetry_is_failure": False,
            },
        ],
    }
    assert summary["replay"]["orchestrator_context_run_ids"] == []
    assert "not production monitoring" in summary["notes"][2]


def test_load_runtime_telemetry_history_rejects_unknown_schema(tmp_path):
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps(
            {
                "schema_version": "edgeenv.runtime-telemetry-history.v0",
                "summary": {},
                "runs": [],
                "missing_telemetry": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="Unsupported runtime telemetry history schema",
    ):
        load_runtime_telemetry_history(history_path)


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


def test_cli_runs_telemetry_inspect_history_validates_replay_artifact(
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
        run_id="run-cli-without-telemetry",
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-cli-telemetry",
        runtime_telemetry=_runtime_telemetry_payload(),
    )
    output_path = tmp_path / "runtime-telemetry-history.json"
    write_runtime_telemetry_history(edgeenv_root, output_path)

    result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "inspect-history",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Runtime telemetry history valid" in result.output
    assert "Replay runs: 1" in result.output
    assert "Telemetry fields:" in result.output
    assert "Telemetry coverage runs: 1" in result.output
    assert "Telemetry coverage missing fields: queue_depth" in result.output
    assert "latency" in result.output
    assert "Evidence gaps: 1" in result.output
    assert "run-cli-without-telemetry" in result.output
    assert "not production monitoring" in result.output


def test_cli_runs_telemetry_inspect_history_json_output(
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
        run_id="run-cli-json",
        runtime_telemetry=_runtime_telemetry_payload(sequence_id=3),
    )
    output_path = tmp_path / "runtime-telemetry-history.json"
    write_runtime_telemetry_history(edgeenv_root, output_path)

    result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "inspect-history",
            str(output_path),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["replay"]["run_ids"] == ["run-cli-json"]
    assert payload["replay"]["execution_sequence_ids"] == [3]
    assert payload["replay"]["telemetry_coverage"]["runs_with_coverage"] == 1
    assert payload["replay"]["telemetry_coverage"]["missing_fields"] == [
        "queue_depth"
    ]
    assert payload["replay"]["telemetry_coverage"]["missing_field_runs"] == [
        {
            "run_id": "run-cli-json",
            "missing_fields": ["queue_depth"],
            "missing_field_count": 1,
            "missing_telemetry_is_failure": False,
        }
    ]


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
        "coverage": {
            "schema_version": "inferedge-runtime-telemetry-coverage-v1",
            "expected_fields": ["queue_depth", "gpu_temperature"],
            "observed_fields": ["gpu_temperature"],
            "missing_fields": ["queue_depth"],
            "expected_field_count": 2,
            "observed_field_count": 1,
            "missing_field_count": 1,
            "coverage_ratio": 0.5,
            "comparability_owner": "edgeenv",
            "missing_telemetry_is_failure": False,
        },
        "missing_fields": ["queue_depth"],
        "production_monitoring": False,
    }


def _orchestrator_feed_payload(run_id: str) -> dict:
    return {
        "schema_version": ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
        "role": "orchestrator_operation_context_for_edgeenv",
        "source": "orchestration_summary",
        "run_id": run_id,
        "not_a_regression_judgement": True,
        "not_a_comparability_gate": True,
        "decision_owner": "lab",
        "regression_owner": "edgeenv",
        "candidate_context": {
            "run_id": run_id,
            "result_telemetry_present": True,
            "history_entry_present": True,
            "telemetry_source": "inferedge_orchestrator_operation_summary",
            "available_sections": [
                "operation",
                "resource",
                "queue_state_summary",
            ],
            "queue_depth": 7,
            "operation": {
                "queue_depth": 7,
                "deadline_missed_count": 2,
                "fallback_count": 1,
            },
            "resource": {
                "source": "tegrastats_timeline",
                "resource_evidence_available": True,
                "gpu_temperature": 78.5,
                "ram_used_mb": 2048.0,
            },
        },
        "edgeenv_mapping_hint": {
            "runtime_telemetry_context_role": "candidate",
            "copy_candidate_context_to": "runtime_telemetry_context.candidate",
        },
    }
