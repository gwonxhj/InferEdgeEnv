from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from inferedge_env.cli import app
from inferedge_env.result.lab_handoff import (
    RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION,
    RuntimeIntelligenceLabHandoffError,
    build_runtime_intelligence_lab_handoff_manifest,
)
from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
)


def test_runtime_intelligence_lab_handoff_manifest_records_producer_contracts(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )

    payload = build_runtime_intelligence_lab_handoff_manifest(
        baseline_result_path=baseline_path,
        candidate_result_path=candidate_path,
        edgeenv_regression_report_path=regression_path,
        telemetry_history_path=history_path,
    )

    assert payload["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert payload["files"] == {
        "baseline_result": str(baseline_path),
        "candidate_result": str(candidate_path),
        "edgeenv_regression_report": str(regression_path),
        "runtime_telemetry_history": str(history_path),
    }
    assert payload["source_repositories"] == {
        "runtime_result": "InferEdge-Runtime",
        "edgeenv_regression_report": "InferEdgeEnv",
        "orchestrator_operation_context": "InferEdgeOrchestrator",
        "lab_report_owner": "InferEdgeLab",
    }
    assert payload["artifact_roles"]["edgeenv_regression_report"] == (
        "edgeenv-comparability-first-runtime-regression-report"
    )
    assert payload["producer_contracts"] == {
        "runtime_result_contract": "lab-compatible-runtime-result-json",
        "edgeenv_history_schema": "edgeenv.runtime-telemetry-history.v1",
        "runtime_telemetry_history_seed_schema": (
            "inferedge-runtime-telemetry-history-seed-v1"
        ),
        "orchestrator_feed_schema": (
            "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1"
        ),
    }
    assert payload["lab_bundle_alignment"]["bundle_schema_version"] == (
        "inferedge.runtime-intelligence-artifact-bundle.v1"
    )
    assert payload["lab_bundle_alignment"]["required_file_keys"] == [
        "baseline_result",
        "candidate_result",
        "edgeenv_regression_report",
        "aiguard_guard_analysis",
    ]
    assert payload["lab_bundle_alignment"]["edgeenv_produced_file_keys"] == [
        "baseline_result",
        "candidate_result",
        "edgeenv_regression_report",
        "runtime_telemetry_history",
    ]
    assert payload["lab_bundle_alignment"]["external_file_keys"] == [
        "aiguard_guard_analysis"
    ]
    assert payload["lab_bundle_alignment"]["source_repositories"][
        "aiguard_guard_analysis"
    ] == "InferEdgeAIGuard"
    assert payload["lab_bundle_alignment"]["artifact_roles"][
        "aiguard_guard_analysis"
    ] == "aiguard-deterministic-runtime-anomaly-evidence"
    assert payload["lab_bundle_alignment"]["producer_contracts"][
        "aiguard_schema"
    ] == "inferedge-aiguard-diagnosis-v1"
    assert payload["lab_bundle_alignment"]["boundary_flags"] == {
        "orchestrator_context_is_verdict": False,
        "orchestrator_context_is_comparability_gate": False,
        "aiguard_guard_analysis_is_external": True,
        "aiguard_is_final_decision_owner": False,
        "edgeenv_does_not_generate_guard_analysis": True,
        "lab_is_final_decision_owner": True,
        "production_observability_platform": False,
    }
    assert payload["boundaries"]["orchestrator_context_is_verdict"] is False
    assert payload["boundaries"]["lab_is_final_decision_owner"] is True
    assert payload["edgeenv_report_summary"] == {
        "baseline_run_id": "baseline",
        "candidate_run_id": "candidate",
        "comparable": True,
        "mode": "same-condition",
        "regression_detected": True,
        "regression_type": "mixed",
        "severity": "high",
        "runtime_telemetry_context_present": True,
        "history_seed_runs": 2,
        "history_seed_run_config_runs": 2,
        "history_seed_run_config_marker_fields": [
            "input_mode",
            "input_preprocess",
            "power_mode",
            "jetson_clocks",
            "warmup",
            "runs",
        ],
        "history_seed_run_config_markers": [
            {
                "run_id": "baseline",
                "shape": "1x640x640",
                "input_mode": "dummy",
                "input_preprocess": "none",
                "power_mode": "unknown",
                "jetson_clocks": "unknown",
                "warmup": 1,
                "runs": 10,
            },
            {
                "run_id": "candidate",
                "shape": "1x640x640",
                "input_mode": "dummy",
                "input_preprocess": "none",
                "power_mode": "unknown",
                "jetson_clocks": "unknown",
                "warmup": 1,
                "runs": 10,
            },
        ],
        "orchestrator_context_present": True,
        "device_local_producer_context_present": True,
        "device_local_producer_context_run_ids": ["candidate"],
    }
    assert "AIGuard guard_analysis is intentionally not produced by EdgeEnv." in (
        payload["notes"]
    )


def test_runtime_intelligence_lab_handoff_cli_writes_manifest(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    output_path = tmp_path / "edgeenv-lab-handoff.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "report",
            "runtime-intelligence-handoff",
            "--baseline-result",
            str(baseline_path),
            "--candidate-result",
            str(candidate_path),
            "--edgeenv-regression-report",
            str(regression_path),
            "--telemetry-history",
            str(history_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Runtime Intelligence handoff manifest written" in result.output
    assert "Lab remains the final deployment decision owner." in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert payload["edgeenv_report_summary"]["history_seed_runs"] == 2
    assert payload["edgeenv_report_summary"]["history_seed_run_config_runs"] == 2
    assert "History seed entries: 2" in result.output
    assert "History seed run_config markers: baseline, candidate" in result.output
    assert "Device-local producer contexts: candidate" in result.output


def test_runtime_intelligence_lab_handoff_rejects_mismatched_run_id(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["candidate_run_id"] = "other-candidate"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_run_id does not match",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_history_seed(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    candidate_seed = regression["runtime_telemetry_context"]["history"]["runs"][1][
        "runtime_telemetry_history_seed"
    ]
    candidate_seed["registry_owner"] = "runtime"
    candidate_seed["decision_owner"] = "aiguard"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="registry_owner must be edgeenv",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_seed_count_mismatch(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["history"]["summary"][
        "history_seed_runs"
    ] = 1
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="history_seed_runs must match preserved seed count",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_seed_run_config(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    candidate_seed = regression["runtime_telemetry_context"]["history"]["runs"][1][
        "runtime_telemetry_history_seed"
    ]
    candidate_seed["run_config"]["runs"] = "10"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=r"run_config\.runs must be an integer",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_history_seed_run_config(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    candidate_seed = history["runs"][1]["runtime_telemetry_history_seed"]
    candidate_seed["run_config"]["timeout_ms"] = "5000"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=r"run_config\.timeout_ms must be an integer or null",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_schema(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["schema_version"] = "unknown"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="orchestrator_operation_context.schema_version",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_producer_marker(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["artifact_role"] = "lab-owned-deployment-risk-report"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="artifact_role must be orchestrator-supplemental-operation-context",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["coverage_summary_owner"] = "orchestrator"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="coverage_summary_owner must be edgeenv",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_incomplete_mapping_required_fields(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["candidate_context_required_fields"] = [
        "run_id",
        "operation",
        "resource",
    ]
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_context_required_fields must include telemetry_source",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_incomplete_aiguard_candidates(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["aiguard_evidence_candidates"] = [
        "runtime_queue_overload"
    ]
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="aiguard_evidence_candidates must include runtime_thermal_instability",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_missing_device_local_producer(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"].pop("producer")
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer is required for device-local lineage",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_unmapped_regression_device_source(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    producer = regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["producer"]
    producer["producer_sources_by_task"] = {
        "vision_agent": ["orchestration_summary"],
    }
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=(
            "device_local_producer_sources must also appear in "
            "producer_sources_by_task"
        ),
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_stage_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    producer = regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["producer"]
    producer["producer_stage_by_task"] = {"vision_agent": ""}
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer_stage_by_task.vision_agent must be a non-empty string",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_history_missing_device_local_producer(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history["runs"][1]["orchestrator_operation_context"]["candidate_context"].pop(
        "producer"
    )
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_context.producer is required",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_history_stage_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    producer = history["runs"][1]["orchestrator_operation_context"][
        "candidate_context"
    ]["producer"]
    producer["producer_stage_by_task"] = {"vision_agent": ""}
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer_stage_by_task.vision_agent must be a non-empty string",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def _write_handoff_files(tmp_path):
    baseline_path = tmp_path / "baseline-result.json"
    candidate_path = tmp_path / "candidate-result.json"
    regression_path = tmp_path / "edgeenv-regression.json"
    history_path = tmp_path / "runtime-telemetry-history.json"
    baseline_path.write_text(json.dumps({"run_id": "baseline"}), encoding="utf-8")
    candidate_path.write_text(json.dumps({"run_id": "candidate"}), encoding="utf-8")
    operation_context = _orchestrator_operation_context("candidate")
    history_path.write_text(
        json.dumps(
            {
                "schema_version": "edgeenv.runtime-telemetry-history.v1",
                "summary": {
                    "registered_runs": 2,
                    "telemetry_runs": 2,
                    "missing_telemetry_runs": 0,
                    "orchestrator_feed_runs": 1,
                    "history_seed_runs": 2,
                    "history_seed_run_config_runs": 2,
                },
                "runs": [
                    {
                        "run_id": "baseline",
                        "runtime_telemetry_history_seed": _runtime_history_seed(
                            "baseline",
                            sequence_id=1,
                        ),
                    },
                    {
                        "run_id": "candidate",
                        "runtime_telemetry_history_seed": _runtime_history_seed(
                            "candidate",
                            sequence_id=2,
                        ),
                        "orchestrator_operation_context": operation_context,
                    },
                ],
                "missing_telemetry": [],
            }
        ),
        encoding="utf-8",
    )
    regression_path.write_text(
        json.dumps(
            {
                "baseline_run_id": "baseline",
                "candidate_run_id": "candidate",
                "comparable": True,
                "mode": "same-condition",
                "regression_detected": True,
                "regression_type": "mixed",
                "severity": "high",
                "runtime_telemetry_context": {
                    "history": {
                        "schema_version": "edgeenv.runtime-telemetry-history.v1",
                        "summary": {
                            "registered_runs": 2,
                            "telemetry_runs": 2,
                            "missing_telemetry_runs": 0,
                            "orchestrator_feed_runs": 1,
                            "history_seed_runs": 2,
                            "history_seed_run_config_runs": 2,
                        },
                        "runs": [
                            {
                                "run_id": "baseline",
                                "runtime_telemetry_history_seed": (
                                    _runtime_history_seed(
                                        "baseline",
                                        sequence_id=1,
                                    )
                                ),
                            },
                            {
                                "run_id": "candidate",
                                "runtime_telemetry_history_seed": (
                                    _runtime_history_seed(
                                        "candidate",
                                        sequence_id=2,
                                    )
                                ),
                                "orchestrator_operation_context": operation_context,
                            },
                        ],
                    },
                    "baseline": {"run_id": "baseline"},
                    "candidate": {
                        "run_id": "candidate",
                        "orchestrator_operation_context": operation_context,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return baseline_path, candidate_path, regression_path, history_path


def _orchestrator_operation_context(run_id: str) -> dict:
    return {
        "schema_version": "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1",
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
        "not_a_regression_judgement": True,
        "not_a_comparability_gate": True,
        "decision_owner": "lab",
        "regression_owner": "edgeenv",
        "candidate_context": {
            "run_id": run_id,
            "telemetry_source": "inferedge_orchestrator_operation_summary",
            "operation": {"queue_depth": 7},
            "resource": {"source": "tegrastats_timeline"},
            "producer": {
                "operation_context_role": "supplemental",
                "producer_sources": [
                    "device_local_cli_override",
                    "orchestration_summary",
                ],
                "device_local_producer_sources": ["device_local_cli_override"],
                "producer_sources_by_task": {
                    "vision_agent": ["device_local_cli_override"],
                },
                "producer_stage_by_task": {
                    "vision_agent": "device_local_starter",
                },
                "producer_event_count": 4,
                "device_local_event_count": 2,
                "device_local_task_count": 1,
            },
        },
        "edgeenv_mapping_hint": {
            "runtime_telemetry_context_role": "candidate",
            "copy_candidate_context_to": "runtime_telemetry_context.candidate",
            "operation_context_role": "supplemental",
            "coverage_summary_owner": "edgeenv",
            "coverage_summary_path": (
                "runtime_telemetry_context.history.telemetry_coverage"
            ),
            "candidate_context_required_fields": [
                "run_id",
                "telemetry_source",
                "operation",
                "resource",
            ],
            "aiguard_evidence_candidates": [
                "runtime_queue_overload",
                "runtime_thermal_instability",
            ],
        },
    }


def _runtime_history_seed(run_id: str, *, sequence_id: int) -> dict:
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
            "run_id": run_id,
            "compare_key": "yolov8n__b1__h640w640__fp32",
            "backend_key": "onnxruntime__cpu",
            "engine_backend": "onnxruntime",
            "device": "cpu",
            "precision": "fp32",
            "power_mode": "unknown",
        },
        "run_config": {
            "batch": 1,
            "height": 640,
            "width": 640,
            "warmup": 1,
            "runs": 10,
            "timeout_ms": None,
            "input_mode": "dummy",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown",
        },
        "points": [
            {
                "execution_sequence_id": sequence_id,
                "telemetry_timestamp": f"2026-05-21T00:00:0{sequence_id}Z",
                "mean_ms": 100.0 + sequence_id,
                "p99_ms": 130.0 + sequence_id,
                "timeout_observed": False,
            }
        ],
    }
