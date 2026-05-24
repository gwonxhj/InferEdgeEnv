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
        "orchestrator_context_present": True,
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
    assert "History seed entries: 2" in result.output


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


def _write_handoff_files(tmp_path):
    baseline_path = tmp_path / "baseline-result.json"
    candidate_path = tmp_path / "candidate-result.json"
    regression_path = tmp_path / "edgeenv-regression.json"
    history_path = tmp_path / "runtime-telemetry-history.json"
    baseline_path.write_text(json.dumps({"run_id": "baseline"}), encoding="utf-8")
    candidate_path.write_text(json.dumps({"run_id": "candidate"}), encoding="utf-8")
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
                            },
                        ],
                    },
                    "baseline": {"run_id": "baseline"},
                    "candidate": {
                        "run_id": "candidate",
                        "orchestrator_operation_context": {
                            "schema_version": (
                                "inferedge-orchestrator-edgeenv-runtime-telemetry-"
                                "feed-v1"
                            ),
                            "not_a_regression_judgement": True,
                            "not_a_comparability_gate": True,
                            "decision_owner": "lab",
                            "regression_owner": "edgeenv",
                            "candidate_context": {
                                "run_id": "candidate",
                                "telemetry_source": (
                                    "inferedge_orchestrator_operation_summary"
                                ),
                                "operation": {"queue_depth": 7},
                                "resource": {"source": "tegrastats_timeline"},
                            },
                            "edgeenv_mapping_hint": {
                                "runtime_telemetry_context_role": "candidate",
                                "copy_candidate_context_to": (
                                    "runtime_telemetry_context.candidate"
                                ),
                                "operation_context_role": "supplemental",
                                "coverage_summary_owner": "edgeenv",
                                "coverage_summary_path": (
                                    "runtime_telemetry_context.history."
                                    "telemetry_coverage"
                                ),
                                "candidate_context_required_fields": [
                                    "run_id",
                                    "telemetry_source",
                                    "operation",
                                    "resource",
                                ],
                            },
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return baseline_path, candidate_path, regression_path, history_path


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
