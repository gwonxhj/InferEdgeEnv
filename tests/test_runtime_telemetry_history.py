from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from helpers import make_result
from inferedge_env.cli import app
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES,
    ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
    ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
    ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
    ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
    ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS,
    ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE,
    ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY,
    ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
    ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
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
        "history_seed_runs": 1,
        "history_seed_run_config_runs": 1,
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
    assert payload["runs"][0]["runtime_telemetry_history_seed"] == (
        payload["runs"][0]["runtime_telemetry"]["history_seed"]
    )
    assert payload["runs"][0]["runtime_telemetry_history_seed"]["registry_owner"] == (
        "edgeenv"
    )
    assert payload["runs"][0]["runtime_telemetry_history_seed"]["decision_owner"] == (
        "lab"
    )
    assert payload["runs"][0]["runtime_telemetry_history_seed"]["run_config"] == {
        "batch": 1,
        "height": 224,
        "width": 224,
        "warmup": 1,
        "runs": 10,
        "timeout_ms": None,
        "input_mode": "dummy",
        "input_preprocess": "none",
        "power_mode": "unknown",
        "jetson_clocks": "unknown",
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
    assert payload["summary"]["history_seed_runs"] == 1
    assert payload["summary"]["history_seed_run_config_runs"] == 1
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
    assert context["source_repository"] == ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY
    assert context["artifact_role"] == ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE
    assert context["producer_contract"] == ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT
    assert context["not_a_regression_judgement"] is True
    assert context["not_a_comparability_gate"] is True
    assert context["decision_owner"] == "lab"
    assert context["regression_owner"] == "edgeenv"
    assert context["candidate_context"]["operation"]["queue_depth"] == 7
    assert context["candidate_context"]["resource"]["gpu_temperature"] == 78.5
    producer = context["candidate_context"]["producer"]
    assert producer["producer_sources"] == [
        "image_file",
        "fastapi_request_fixture",
        "resource_snapshot_fixture",
    ]
    assert producer["producer_sources_by_task"] == {
        "vision_agent": ["image_file"],
        "voice_command_agent": ["fastapi_request_fixture"],
        "safety_monitor_agent": ["resource_snapshot_fixture"],
    }
    assert producer["producer_stage_by_task"] == {
        "vision_agent": "device_local_cli_override",
        "voice_command_agent": "device_local_cli_override",
        "safety_monitor_agent": "device_local_cli_override",
    }
    assert producer["device_local_event_count"] == 15
    assert producer["operation_context_role"] == "supplemental"
    assert context["edgeenv_mapping_hint"]["copy_candidate_context_to"] == (
        ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH
    )
    assert context["edgeenv_mapping_hint"]["operation_context_role"] == (
        ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE
    )
    assert context["edgeenv_mapping_hint"]["coverage_summary_owner"] == (
        ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER
    )
    assert context["edgeenv_mapping_hint"]["coverage_summary_path"] == (
        ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH
    )
    assert context["edgeenv_mapping_hint"]["candidate_context_required_fields"] == [
        *ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS
    ]
    assert context["edgeenv_mapping_hint"]["aiguard_evidence_candidates"] == [
        *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
    ]
    assert context["downstream_guard_alignment"][
        "producer_lineage_evidence_type"
    ] == ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    assert context["downstream_guard_alignment"][
        "operation_evidence_candidates"
    ] == [*ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES]
    assert context["downstream_guard_alignment"][
        "orchestrator_is_final_decision_owner"
    ] is False
    assert context["downstream_guard_alignment"][
        "lab_is_final_decision_owner"
    ] is True
    for field in ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS:
        assert field in context["candidate_context"]
    assert "not a regression judgement" in payload["notes"][3]
    strict_summary = inspect_runtime_telemetry_history(
        payload,
        require_device_local_producer=True,
    )
    assert strict_summary["replay"]["device_local_producer_context_run_ids"] == [
        "candidate"
    ]
    assert strict_summary["replay"][
        "producer_lineage_guard_alignment_run_ids"
    ] == ["candidate"]


def test_build_runtime_telemetry_history_preserves_missing_orchestrator_feed_context(
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
    summary = inspect_runtime_telemetry_history(payload)

    assert payload["summary"]["telemetry_runs"] == 0
    assert payload["summary"]["missing_telemetry_runs"] == 1
    assert payload["summary"]["orchestrator_feed_runs"] == 1
    context = payload["missing_telemetry"][0]["orchestrator_operation_context"]
    assert context["source_repository"] == ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY
    assert context["artifact_role"] == ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE
    assert context["producer_contract"] == ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT
    assert context["candidate_context"]["producer"]["producer_stage_by_task"] == {
        "vision_agent": "device_local_cli_override",
        "voice_command_agent": "device_local_cli_override",
        "safety_monitor_agent": "device_local_cli_override",
    }
    assert context["edgeenv_mapping_hint"]["aiguard_evidence_candidates"] == [
        *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
    ]
    assert context["downstream_guard_alignment"][
        "producer_lineage_evidence_type"
    ] == ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    assert summary["replay"]["orchestrator_context_run_ids"] == ["candidate"]
    assert summary["replay"]["missing_orchestrator_context_run_ids"] == [
        "candidate"
    ]
    strict_summary = inspect_runtime_telemetry_history(
        payload,
        require_device_local_producer=True,
    )
    assert strict_summary["replay"]["device_local_producer_context_run_ids"] == [
        "candidate"
    ]
    assert strict_summary["replay"][
        "producer_lineage_guard_alignment_run_ids"
    ] == ["candidate"]


def test_inspect_runtime_telemetry_history_requires_device_local_producer(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["candidate_context"].pop("producer")
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")
    payload = build_runtime_telemetry_history(
        edgeenv_root,
        generated_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
        orchestrator_feeds=[feed_path],
    )

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="candidate_context.producer is required",
    ):
        inspect_runtime_telemetry_history(
            payload,
            require_device_local_producer=True,
        )


def test_inspect_runtime_telemetry_history_rejects_unmapped_device_local_source(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["candidate_context"]["producer"]["producer_sources_by_task"] = {
        "vision_agent": ["orchestration_summary"],
    }
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match=(
            "device_local_producer_sources must also appear in "
            "producer_sources_by_task"
        ),
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            generated_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
            orchestrator_feeds=[feed_path],
        )


def test_inspect_runtime_telemetry_history_rejects_empty_stage_mapping(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["candidate_context"]["producer"]["producer_stage_by_task"] = {
        "vision_agent": "",
    }
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="producer_stage_by_task.vision_agent must be a non-empty string",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            generated_at=datetime(2026, 5, 22, tzinfo=timezone.utc),
            orchestrator_feeds=[feed_path],
        )


def test_inspect_runtime_telemetry_history_requires_orchestrator_context():
    payload = {
        "schema_version": RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
        "summary": {
            "registered_runs": 0,
            "telemetry_runs": 0,
            "missing_telemetry_runs": 0,
            "orchestrator_feed_runs": 0,
        },
        "runs": [],
        "missing_telemetry": [],
    }

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="must include at least one orchestrator_operation_context",
    ):
        inspect_runtime_telemetry_history(
            payload,
            require_device_local_producer=True,
        )


def test_load_runtime_telemetry_history_rejects_bad_missing_orchestrator_marker(
    tmp_path,
):
    history_path = tmp_path / "history.json"
    payload = {
        "schema_version": RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
        "summary": {
            "registered_runs": 1,
            "telemetry_runs": 0,
            "missing_telemetry_runs": 1,
            "orchestrator_feed_runs": 1,
        },
        "runs": [],
        "missing_telemetry": [
            {
                "run_id": "candidate",
                "reason": "runtime_telemetry_missing",
                "orchestrator_operation_context": _orchestrator_feed_payload(
                    "candidate"
                ),
            }
        ],
    }
    payload["missing_telemetry"][0]["orchestrator_operation_context"][
        "artifact_role"
    ] = "lab-owned-deployment-risk-report"
    history_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match=(
            "missing_telemetry\\[0\\].orchestrator_operation_context."
            "artifact_role must be orchestrator-supplemental-operation-context"
        ),
    ):
        load_runtime_telemetry_history(history_path)


def test_build_runtime_telemetry_history_rejects_bad_orchestrator_producer_context(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["candidate_context"]["producer"]["operation_context_role"] = "verdict"
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="candidate_context.producer.operation_context_role must be supplemental",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_build_runtime_telemetry_history_rejects_bad_feed_mapping_contract(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["edgeenv_mapping_hint"]["coverage_summary_owner"] = "orchestrator"
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="coverage_summary_owner must be edgeenv",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_build_runtime_telemetry_history_rejects_bad_orchestrator_producer_marker(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["artifact_role"] = "lab-owned-deployment-risk-report"
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="artifact_role must be orchestrator-supplemental-operation-context",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_build_runtime_telemetry_history_rejects_incomplete_aiguard_candidates(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["edgeenv_mapping_hint"]["aiguard_evidence_candidates"] = [
        "runtime_queue_overload"
    ]
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="aiguard_evidence_candidates must include runtime_thermal_instability",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_build_runtime_telemetry_history_rejects_missing_guard_alignment(
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
    feed = _orchestrator_feed_payload("candidate")
    feed.pop("downstream_guard_alignment")
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="downstream_guard_alignment is required",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


def test_build_runtime_telemetry_history_rejects_bad_guard_alignment(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["downstream_guard_alignment"][
        "producer_lineage_evidence_type"
    ] = "runtime_queue_overload"
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match=(
            "producer_lineage_evidence_type must be "
            "edgeenv_orchestrator_producer_lineage"
        ),
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
        )


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


def test_build_runtime_telemetry_history_rejects_bad_runtime_history_seed(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    edgeenv_root = tmp_path / ".edgeenv"
    telemetry = _runtime_telemetry_payload(sequence_id=2)
    telemetry["history_seed"]["registry_owner"] = "runtime"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-with-bad-seed",
        runtime_telemetry=telemetry,
    )

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match="history seed registry_owner must be edgeenv",
    ):
        build_runtime_telemetry_history(edgeenv_root)


def test_build_runtime_telemetry_history_rejects_bad_runtime_seed_run_config(
    tmp_path,
    bench_config,
    target_profile,
    config_files,
):
    edgeenv_root = tmp_path / ".edgeenv"
    telemetry = _runtime_telemetry_payload(sequence_id=2)
    telemetry["history_seed"]["run_config"]["runs"] = "10"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        config_files,
        run_id="run-with-bad-seed-run-config",
        runtime_telemetry=telemetry,
    )

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match=r"run_config\.runs must be an integer",
    ):
        build_runtime_telemetry_history(edgeenv_root)


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
            "--require-device-local-producer",
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    assert "Orchestrator context entries: 1" in export_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Orchestrator context runs: 1" in inspect_result.output
    assert "Device-local producer context runs: 1" in inspect_result.output
    assert "Producer-lineage guard alignment runs: 1" in inspect_result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["runs"][0]["orchestrator_operation_context"]["run_id"] == (
        "candidate"
    )
    assert payload["runs"][0]["orchestrator_operation_context"][
        "source_repository"
    ] == ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY
    assert payload["runs"][0]["orchestrator_operation_context"][
        "downstream_guard_alignment"
    ]["producer_lineage_evidence_type"] == (
        ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    )
    remote_summary = payload["runs"][0]["orchestrator_operation_context"][
        "remote_runtime_event_summary"
    ]
    assert remote_summary["evidence_role"] == (
        ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE
    )
    assert remote_summary["operation_boundary"] == (
        ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY
    )
    assert remote_summary["production_remote_execution"] is False


def test_cli_runs_telemetry_export_history_preserves_missing_orchestrator_feed(
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
    assert "Telemetry entries: 0" in export_result.output
    assert "Missing telemetry: 1" in export_result.output
    assert "Orchestrator context entries: 1" in export_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Replay runs: 0" in inspect_result.output
    assert "Orchestrator context runs: 1" in inspect_result.output
    assert "Missing telemetry Orchestrator context runs: 1" in inspect_result.output
    assert "Evidence gaps: 1" in inspect_result.output
    assert "Missing run IDs: candidate" in inspect_result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    missing_context = payload["missing_telemetry"][0]["orchestrator_operation_context"]
    assert missing_context["run_id"] == "candidate"
    assert missing_context["source_repository"] == (
        ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY
    )
    assert missing_context["artifact_role"] == ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE
    assert missing_context["producer_contract"] == (
        ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT
    )
    assert missing_context["not_a_regression_judgement"] is True
    assert missing_context["not_a_comparability_gate"] is True
    assert missing_context["remote_runtime_event_summary"]["evidence_role"] == (
        ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE
    )


def test_build_runtime_telemetry_history_rejects_bad_remote_event_summary_role(
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
    feed = _orchestrator_feed_payload("candidate")
    feed["remote_runtime_event_summary"]["evidence_role"] = (
        "production_remote_execution_summary"
    )
    feed_path = tmp_path / "orchestrator-feed.json"
    feed_path.write_text(json.dumps(feed), encoding="utf-8")

    with pytest.raises(
        RuntimeTelemetryHistoryError,
        match=r"remote_runtime_event_summary\.evidence_role",
    ):
        build_runtime_telemetry_history(
            edgeenv_root,
            orchestrator_feeds=[feed_path],
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
    assert summary["replay"]["history_seed_run_ids"] == ["run-a", "run-b"]
    assert summary["replay"]["history_seed_run_config_run_ids"] == [
        "run-a",
        "run-b",
    ]
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
    assert "History seed entries: 1" in result.output
    assert "History seed run_config entries: 1" in result.output
    assert "not production monitoring" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["summary"]["telemetry_runs"] == 1
    assert payload["summary"]["history_seed_runs"] == 1
    assert payload["summary"]["history_seed_run_config_runs"] == 1
    assert payload["runs"][0]["run_id"] == "run-cli-telemetry"
    assert payload["runs"][0]["runtime_telemetry_history_seed"]["registry_owner"] == (
        "edgeenv"
    )


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
    assert "Runtime history seed runs: 1" in result.output
    assert "Runtime history seed run_config runs: 1" in result.output
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
    assert payload["replay"]["history_seed_run_ids"] == ["run-cli-json"]
    assert payload["replay"]["history_seed_run_config_run_ids"] == [
        "run-cli-json"
    ]
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
    payload = {
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
    payload["history_seed"] = _runtime_history_seed_payload(sequence_id)
    return payload


def _runtime_history_seed_payload(sequence_id: int) -> dict:
    return {
        "schema_version": "inferedge-runtime-telemetry-history-seed-v1",
        "evidence_role": "runtime_telemetry_history_seed",
        "registry_owner": "edgeenv",
        "decision_owner": "lab",
        "source_result_schema_version": "inferedge-runtime-result-v1",
        "source_telemetry_schema_version": "inferedge-runtime-telemetry-v1",
        "replay_scope": "single_result_to_history",
        "replay_ready": True,
        "production_monitoring": False,
        "missing_telemetry_is_failure": False,
        "source_result": {
            "compare_key": "demo__b1__h224w224__fp32",
            "backend_key": "onnxruntime__cpu",
            "engine_backend": "onnxruntime",
            "device": "cpu",
            "precision": "fp32",
            "power_mode": "unknown",
        },
        "run_config": {
            "batch": 1,
            "height": 224,
            "width": 224,
            "warmup": 1,
            "runs": 10,
            "timeout_ms": None,
            "input_mode": "dummy",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown",
        },
        "recommended_registry_key_fields": [
            "compare_key",
            "backend_key",
            "device",
            "precision",
            "power_mode",
            "run_config",
        ],
        "time_series_fields": [
            "telemetry_timestamp",
            "execution_sequence_id",
            "latency.mean_ms",
            "operation.timeout_observed",
        ],
        "points": [
            {
                "execution_sequence_id": sequence_id,
                "telemetry_timestamp": "2026-05-22T00:00:00Z",
                "mean_ms": 10.0,
                "p99_ms": 12.0,
                "timeout_observed": False,
            }
        ],
    }


def _orchestrator_feed_payload(run_id: str) -> dict:
    return {
        "schema_version": ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
        "role": "orchestrator_operation_context_for_edgeenv",
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
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
                "producer",
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
            "producer": {
                "producer_sources": [
                    "image_file",
                    "fastapi_request_fixture",
                    "resource_snapshot_fixture",
                ],
                "device_local_producer_sources": [
                    "image_file",
                    "fastapi_request_fixture",
                    "resource_snapshot_fixture",
                ],
                "producer_sources_by_task": {
                    "vision_agent": ["image_file"],
                    "voice_command_agent": ["fastapi_request_fixture"],
                    "safety_monitor_agent": ["resource_snapshot_fixture"],
                },
                "producer_stage_by_task": {
                    "vision_agent": "device_local_cli_override",
                    "voice_command_agent": "device_local_cli_override",
                    "safety_monitor_agent": "device_local_cli_override",
                },
                "producer_event_count": 7,
                "device_local_event_count": 15,
                "device_local_task_count": 3,
                "operation_context_role": "supplemental",
            },
        },
        "edgeenv_mapping_hint": {
            "runtime_telemetry_context_role": "candidate",
            "copy_candidate_context_to": ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
            "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
            "coverage_summary_owner": ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
            "coverage_summary_path": ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
            "candidate_context_required_fields": [
                "run_id",
                "telemetry_source",
                "operation",
                "resource",
            ],
            "aiguard_evidence_candidates": [
                *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            ],
        },
        "downstream_guard_alignment": {
            "declared_by": "orchestrator",
            "producer_lineage_evidence_type": (
                ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
            ),
            "operation_evidence_candidates": [
                *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            ],
            "validated_by": [
                "edgeenv runs telemetry inspect-history",
                "inferedge-aiguard reason-edgeenv-regression",
                "inferedgelab runtime-intelligence bundle manifest gate",
            ],
            "orchestrator_is_final_decision_owner": False,
            "lab_is_final_decision_owner": True,
        },
        "remote_runtime_event_summary": {
            "event_count": 4,
            "runtime_event_count": 4,
            "production_remote_execution": False,
            "evidence_role": ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE,
            "operation_boundary": ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY,
        },
    }
