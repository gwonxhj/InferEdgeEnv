from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES,
    ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
    ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
    ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
    ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
    ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS,
    ORCHESTRATOR_POLICY_PRESSURE_SUMMARY_SCHEMA_VERSION,
    ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE,
    ORCHESTRATOR_STALE_DROP_SUMMARY_SCHEMA_VERSION,
    ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
    ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
    RuntimeTelemetryHistoryError,
    RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
    RUNTIME_TELEMETRY_HISTORY_SEED_SCHEMA_VERSION,
    validate_runtime_telemetry_history,
)


RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION = (
    "edgeenv.runtime-intelligence-lab-handoff.v1"
)
LAB_RUNTIME_INTELLIGENCE_BUNDLE_SCHEMA_VERSION = (
    "inferedge.runtime-intelligence-artifact-bundle.v1"
)
AIGUARD_DIAGNOSIS_SCHEMA_VERSION = "inferedge-aiguard-diagnosis-v1"

SOURCE_REPOSITORIES = {
    "runtime_result": "InferEdge-Runtime",
    "edgeenv_regression_report": "InferEdgeEnv",
    "orchestrator_operation_context": "InferEdgeOrchestrator",
    "lab_report_owner": "InferEdgeLab",
}

ARTIFACT_ROLES = {
    "baseline_result": "runtime-lab-compatible-baseline-result",
    "candidate_result": "runtime-lab-compatible-candidate-result",
    "edgeenv_regression_report": (
        "edgeenv-comparability-first-runtime-regression-report"
    ),
    "orchestrator_operation_context": "orchestrator-supplemental-operation-context",
    "lab_report": "lab-owned-deployment-risk-report",
}

PRODUCER_CONTRACTS = {
    "runtime_result_contract": "lab-compatible-runtime-result-json",
    "edgeenv_history_schema": RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
    "runtime_telemetry_history_seed_schema": (
        RUNTIME_TELEMETRY_HISTORY_SEED_SCHEMA_VERSION
    ),
    "orchestrator_feed_schema": ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
}

LAB_BUNDLE_SOURCE_REPOSITORIES = {
    **SOURCE_REPOSITORIES,
    "aiguard_guard_analysis": "InferEdgeAIGuard",
}
LAB_BUNDLE_ARTIFACT_ROLES = {
    **ARTIFACT_ROLES,
    "aiguard_guard_analysis": "aiguard-deterministic-runtime-anomaly-evidence",
}
LAB_BUNDLE_PRODUCER_CONTRACTS = {
    **PRODUCER_CONTRACTS,
    "aiguard_schema": AIGUARD_DIAGNOSIS_SCHEMA_VERSION,
}
LAB_BUNDLE_EXTERNAL_FILE_KEYS = ("aiguard_guard_analysis",)
LAB_BUNDLE_EXTERNAL_AIGUARD_REQUIRED_EVIDENCE_TYPES = (
    "runtime_telemetry_context_coverage",
    "edgeenv_orchestrator_producer_lineage",
    "edgeenv_orchestrator_operation_risk_rollup",
    "edgeenv_orchestrator_task_event_rollup",
    "edgeenv_orchestrator_operation_timeline_summary",
    "edgeenv_orchestrator_scheduler_fairness_summary",
    "edgeenv_orchestrator_policy_pressure_summary",
    "runtime_history_seed_run_config_traceability",
    "runtime_queue_overload",
    "runtime_thermal_instability",
    "remote_execution_recovered_by_fallback",
)
LAB_BUNDLE_OPTIONAL_AIGUARD_EVIDENCE_TYPES = (
    "stale_frame_risk",
    "edgeenv_orchestrator_stale_drop_summary",
)
LAB_BUNDLE_OPTIONAL_AIGUARD_SOURCE_TRACEABILITY_CONTEXT_ROLE = (
    "read_only_optional_source_traceability"
)
LAB_BUNDLE_OPTIONAL_AIGUARD_STALE_DROP_REPRODUCTION_COMMAND = (
    "python",
    "-m",
    "inferedge_aiguard.cli",
    "build-runtime-intelligence-optional-stale-drop",
    "--edgeenv-regression",
    (
        "examples/runtime_intelligence/"
        "edgeenv_runtime_regression_with_optional_stale_drop_context.json"
    ),
    "--remote-dispatch",
    "examples/runtime_intelligence/remote_dispatch_fallback_recovered_result.json",
    "--orchestration-summary",
    "examples/runtime_intelligence/orchestrator_multi_workload_sustained_summary.json",
    "--save-json",
    (
        "examples/runtime_intelligence/"
        "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
    ),
)
LAB_BUNDLE_EXPECTED_REPORT_MARKERS = (
    "Runtime Intelligence Risk Summary",
    "Runtime replay duration scope",
    "Orchestrator operation feed context",
    "EdgeEnv fixture matrix coverage",
    "Reviewer operation quick scan",
    "Orchestrator task event rollup",
    "Lab EdgeEnv preservation context",
    "AIGuard operation risk rollup evidence",
    "AIGuard task event rollup evidence",
    "AIGuard operation timeline evidence",
    "AIGuard scheduler fairness evidence",
    "AIGuard policy pressure evidence",
    "AIGuard runtime operation anomalies",
    "AIGuard remote dispatch event summary",
    "AIGuard remote event summary consistency",
    "Remote fallback starter evidence",
    "lab=Remote fallback starter evidence; evidence=remote_execution_recovered_by_fallback",
    "AIGuard producer-lineage guard alignment",
    "Lab remains the final deployment decision owner.",
)

BOUNDARIES = {
    "orchestrator_context_is_verdict": False,
    "orchestrator_context_is_comparability_gate": False,
    "edgeenv_is_final_decision_owner": False,
    "lab_is_final_decision_owner": True,
    "production_observability_platform": False,
}

RUN_CONFIG_MARKER_FIELDS = (
    "input_mode",
    "input_preprocess",
    "power_mode",
    "jetson_clocks",
    "warmup",
    "runs",
)


class RuntimeIntelligenceLabHandoffError(ValueError):
    """Raised when an EdgeEnv-to-Lab handoff manifest cannot be built."""


def build_runtime_intelligence_lab_handoff_manifest(
    *,
    baseline_result_path: Path | str,
    candidate_result_path: Path | str,
    edgeenv_regression_report_path: Path | str,
    telemetry_history_path: Path | str | None = None,
) -> dict[str, Any]:
    baseline_path = Path(baseline_result_path)
    candidate_path = Path(candidate_result_path)
    regression_path = Path(edgeenv_regression_report_path)
    history_path = Path(telemetry_history_path) if telemetry_history_path else None

    baseline_result = _load_json_object(baseline_path, "baseline result")
    candidate_result = _load_json_object(candidate_path, "candidate result")
    regression_report = _load_json_object(regression_path, "EdgeEnv regression report")
    history_payload = (
        _load_json_object(history_path, "runtime telemetry history")
        if history_path is not None
        else None
    )

    _validate_run_alignment(
        baseline_result,
        candidate_result,
        regression_report,
        regression_path=regression_path,
    )
    _validate_regression_context(regression_report, regression_path=regression_path)
    if history_payload is not None:
        _validate_telemetry_history(history_payload, history_path=history_path)

    files: dict[str, str] = {
        "baseline_result": str(baseline_path),
        "candidate_result": str(candidate_path),
        "edgeenv_regression_report": str(regression_path),
    }
    if history_path is not None:
        files["runtime_telemetry_history"] = str(history_path)

    return {
        "schema_version": RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION,
        "role": "edgeenv-runtime-intelligence-lab-handoff",
        "description": (
            "EdgeEnv producer-side manifest for a Lab-owned Runtime Intelligence "
            "deployment risk report."
        ),
        "files": files,
        "source_repositories": dict(SOURCE_REPOSITORIES),
        "artifact_roles": dict(ARTIFACT_ROLES),
        "producer_contracts": dict(PRODUCER_CONTRACTS),
        "ownership": {
            "runtime_result_owner": "runtime",
            "regression_owner": "edgeenv",
            "operation_context_owner": "orchestrator",
            "deployment_decision_owner": "lab",
        },
        "boundaries": dict(BOUNDARIES),
        "lab_bundle_alignment": _lab_bundle_alignment(files),
        "edgeenv_report_summary": _edgeenv_report_summary(regression_report),
        "notes": [
            "This manifest is EdgeEnv producer-side handoff metadata.",
            "AIGuard guard_analysis is intentionally not produced by EdgeEnv.",
            "Lab remains the final deployment decision owner.",
            "This is a local artifact contract, not production observability.",
        ],
    }


def write_runtime_intelligence_lab_handoff_manifest(
    *,
    output_path: Path | str,
    baseline_result_path: Path | str,
    candidate_result_path: Path | str,
    edgeenv_regression_report_path: Path | str,
    telemetry_history_path: Path | str | None = None,
) -> dict[str, Any]:
    payload = build_runtime_intelligence_lab_handoff_manifest(
        baseline_result_path=baseline_result_path,
        candidate_result_path=candidate_result_path,
        edgeenv_regression_report_path=edgeenv_regression_report_path,
        telemetry_history_path=telemetry_history_path,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeIntelligenceLabHandoffError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeIntelligenceLabHandoffError(
            f"{label} is invalid JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"{label} must be a JSON object: {path}"
        )
    return payload


def _validate_run_alignment(
    baseline_result: dict[str, Any],
    candidate_result: dict[str, Any],
    regression_report: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    baseline_run_id = _aligned_result_run_id(
        baseline_result,
        fallback=regression_report.get("baseline_run_id"),
        result_label="baseline result",
        regression_field="baseline_run_id",
    )
    candidate_run_id = _aligned_result_run_id(
        candidate_result,
        fallback=regression_report.get("candidate_run_id"),
        result_label="candidate result",
        regression_field="candidate_run_id",
    )
    if regression_report.get("baseline_run_id") != baseline_run_id:
        raise RuntimeIntelligenceLabHandoffError(
            "EdgeEnv regression report baseline_run_id does not match "
            f"baseline result run_id: {regression_path}"
        )
    if regression_report.get("candidate_run_id") != candidate_run_id:
        raise RuntimeIntelligenceLabHandoffError(
            "EdgeEnv regression report candidate_run_id does not match "
            f"candidate result run_id: {regression_path}"
        )


def _aligned_result_run_id(
    result: dict[str, Any],
    *,
    fallback: Any,
    result_label: str,
    regression_field: str,
) -> str:
    result_run_id = result.get("run_id")
    if isinstance(result_run_id, str) and result_run_id:
        return result_run_id
    if result_run_id is not None:
        raise RuntimeIntelligenceLabHandoffError(
            f"{result_label} run_id must be a non-empty string when present"
        )
    if isinstance(fallback, str) and fallback:
        return fallback
    raise RuntimeIntelligenceLabHandoffError(
        f"{result_label} must include run_id or EdgeEnv regression report "
        f"must include a non-empty {regression_field}"
    )


def _validate_regression_context(
    regression_report: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    context = regression_report.get("runtime_telemetry_context")
    if context is None:
        return
    if not isinstance(context, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"runtime_telemetry_context must be an object: {regression_path}"
        )
    history = context.get("history")
    if history is not None:
        if not isinstance(history, dict):
            raise RuntimeIntelligenceLabHandoffError(
                f"runtime_telemetry_context.history must be an object: {regression_path}"
            )
        if history.get("schema_version") != RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION:
            raise RuntimeIntelligenceLabHandoffError(
                "runtime_telemetry_context.history.schema_version must be "
                f"{RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION}"
            )
        _validate_history_seed_summary(
            history,
            label=f"runtime_telemetry_context.history: {regression_path}",
        )

    for label in ("baseline", "candidate"):
        run_context = context.get(label)
        if isinstance(run_context, dict):
            _validate_orchestrator_context(run_context, regression_path=regression_path)


def _validate_orchestrator_context(
    run_context: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    operation_context = run_context.get("orchestrator_operation_context")
    if operation_context is None:
        return
    if not isinstance(operation_context, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"orchestrator_operation_context must be an object: {regression_path}"
        )
    if (
        operation_context.get("schema_version")
        != ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION
    ):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.schema_version must be "
            f"{ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION}"
        )
    _validate_orchestrator_producer_markers(
        operation_context,
        regression_path=regression_path,
    )
    if operation_context.get("not_a_regression_judgement") is not True:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.not_a_regression_judgement must be true"
        )
    if operation_context.get("not_a_comparability_gate") is not True:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.not_a_comparability_gate must be true"
        )
    if operation_context.get("decision_owner") != "lab":
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.decision_owner must be lab"
        )
    if operation_context.get("regression_owner") != "edgeenv":
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.regression_owner must be edgeenv"
        )
    _validate_orchestrator_mapping_hint(
        operation_context.get("edgeenv_mapping_hint"),
        operation_context=operation_context,
        regression_path=regression_path,
    )
    _validate_orchestrator_downstream_guard_alignment(
        operation_context.get("downstream_guard_alignment"),
        regression_path=regression_path,
    )
    _validate_device_local_producer_lineage(
        operation_context.get("candidate_context"),
        label="orchestrator_operation_context.candidate_context",
        source=regression_path,
    )
    _validate_orchestrator_stale_drop_context(
        operation_context,
        regression_path=regression_path,
    )
    _validate_orchestrator_policy_pressure_context(
        operation_context,
        regression_path=regression_path,
    )


def _validate_orchestrator_producer_markers(
    operation_context: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    expected_pairs = {
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    }
    for key, expected in expected_pairs.items():
        if operation_context.get(key) != expected:
            raise RuntimeIntelligenceLabHandoffError(
                f"orchestrator_operation_context.{key} must be {expected}: "
                f"{regression_path}"
            )


def _validate_orchestrator_mapping_hint(
    mapping_hint: Any,
    *,
    operation_context: dict[str, Any],
    regression_path: Path,
) -> None:
    if mapping_hint is None:
        return
    if not isinstance(mapping_hint, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"orchestrator_operation_context.edgeenv_mapping_hint must be an object: "
            f"{regression_path}"
        )
    expected_pairs = {
        "copy_candidate_context_to": ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
        "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        "coverage_summary_owner": ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
        "coverage_summary_path": ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
    }
    for key, expected in expected_pairs.items():
        if key in mapping_hint and mapping_hint.get(key) != expected:
            raise RuntimeIntelligenceLabHandoffError(
                "orchestrator_operation_context.edgeenv_mapping_hint."
                f"{key} must be {expected}: {regression_path}"
            )
    required_fields = mapping_hint.get("candidate_context_required_fields")
    if required_fields is None:
        return
    if not isinstance(required_fields, list) or not all(
        isinstance(item, str) for item in required_fields
    ):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.edgeenv_mapping_hint."
            "candidate_context_required_fields must be a string list: "
            f"{regression_path}"
        )
    missing_required = [
        field
        for field in ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS
        if field not in required_fields
    ]
    if missing_required:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.edgeenv_mapping_hint."
            "candidate_context_required_fields must include "
            f"{', '.join(missing_required)}: {regression_path}"
        )
    evidence_candidates = mapping_hint.get("aiguard_evidence_candidates")
    if evidence_candidates is not None:
        if not isinstance(evidence_candidates, list) or not all(
            isinstance(item, str) for item in evidence_candidates
        ):
            raise RuntimeIntelligenceLabHandoffError(
                "orchestrator_operation_context.edgeenv_mapping_hint."
                "aiguard_evidence_candidates must be a string list: "
                f"{regression_path}"
            )
        missing_candidates = [
            candidate
            for candidate in ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            if candidate not in evidence_candidates
        ]
        if missing_candidates:
            raise RuntimeIntelligenceLabHandoffError(
                "orchestrator_operation_context.edgeenv_mapping_hint."
                "aiguard_evidence_candidates must include "
                f"{', '.join(missing_candidates)}: {regression_path}"
            )
    candidate_context = operation_context.get("candidate_context")
    if not isinstance(candidate_context, dict):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.candidate_context must be an object: "
            f"{regression_path}"
        )
    missing_context = [
        field
        for field in ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS
        if field not in candidate_context
    ]
    if missing_context:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.candidate_context must include "
            f"{', '.join(missing_context)}: {regression_path}"
        )


def _validate_orchestrator_downstream_guard_alignment(
    value: Any,
    *,
    regression_path: Path,
) -> None:
    if not isinstance(value, dict):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment must be "
            f"an object: {regression_path}"
        )
    if value.get("declared_by") != "orchestrator":
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            f"declared_by must be orchestrator: {regression_path}"
        )
    if (
        value.get("producer_lineage_evidence_type")
        != ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    ):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            "producer_lineage_evidence_type must be "
            f"{ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE}: "
            f"{regression_path}"
        )
    operation_candidates = value.get("operation_evidence_candidates")
    if not isinstance(operation_candidates, list) or not all(
        isinstance(item, str) for item in operation_candidates
    ):
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            "operation_evidence_candidates must be a string list: "
            f"{regression_path}"
        )
    missing_candidates = [
        candidate
        for candidate in ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
        if candidate not in operation_candidates
    ]
    if missing_candidates:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            "operation_evidence_candidates must include "
            f"{', '.join(missing_candidates)}: {regression_path}"
        )
    if value.get("orchestrator_is_final_decision_owner") is not False:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            "orchestrator_is_final_decision_owner must be false: "
            f"{regression_path}"
        )
    if value.get("lab_is_final_decision_owner") is not True:
        raise RuntimeIntelligenceLabHandoffError(
            "orchestrator_operation_context.downstream_guard_alignment."
            f"lab_is_final_decision_owner must be true: {regression_path}"
        )


def _validate_telemetry_history(
    history_payload: dict[str, Any],
    *,
    history_path: Path,
) -> None:
    require_device_local_producer = _requires_device_local_producer(history_payload)
    try:
        validate_runtime_telemetry_history(
            history_payload,
            source=history_path,
            require_device_local_producer=require_device_local_producer,
        )
    except RuntimeTelemetryHistoryError as exc:
        raise RuntimeIntelligenceLabHandoffError(
            f"runtime telemetry history is invalid for Lab handoff: {exc}"
        ) from exc
    _validate_history_seed_summary(
        history_payload,
        label=f"runtime telemetry history: {history_path}",
    )


def _validate_history_seed_summary(history: dict[str, Any], *, label: str) -> None:
    runs = history.get("runs")
    summary = history.get("summary")
    if not isinstance(summary, dict):
        return
    expected_seed_runs = summary.get("history_seed_runs")
    if expected_seed_runs is None and runs is None:
        return
    if runs is None:
        if expected_seed_runs in (None, 0):
            return
        raise RuntimeIntelligenceLabHandoffError(
            f"{label} must include runs when history_seed_runs is non-zero"
        )
    if not isinstance(runs, list):
        raise RuntimeIntelligenceLabHandoffError(f"{label}.runs must be a list")
    seed_count = sum(
        1
        for item in runs
        if isinstance(item, dict)
        and isinstance(item.get("runtime_telemetry_history_seed"), dict)
    )
    if expected_seed_runs is not None and expected_seed_runs != seed_count:
        raise RuntimeIntelligenceLabHandoffError(
            f"{label}.summary.history_seed_runs must match preserved seed count"
        )
    expected_seed_run_config_runs = summary.get("history_seed_run_config_runs")
    if expected_seed_run_config_runs is not None:
        seed_run_config_count = sum(
            1
            for item in runs
            if isinstance(item, dict)
            and isinstance(item.get("runtime_telemetry_history_seed"), dict)
            and isinstance(
                item["runtime_telemetry_history_seed"].get("run_config"),
                dict,
            )
        )
        if expected_seed_run_config_runs != seed_run_config_count:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.summary.history_seed_run_config_runs must match "
                "preserved seed run_config count"
            )
    if seed_count:
        _validate_embedded_runtime_history(history, label=label)


def _validate_embedded_runtime_history(history: dict[str, Any], *, label: str) -> None:
    payload = {
        "schema_version": history.get("schema_version"),
        "summary": history.get("summary", {}),
        "runs": history.get("runs", []),
        "missing_telemetry": history.get("missing_telemetry", []),
    }
    if "telemetry_coverage" in history:
        payload["telemetry_coverage"] = history.get("telemetry_coverage")
    require_device_local_producer = _requires_device_local_producer(payload)
    try:
        validate_runtime_telemetry_history(
            payload,
            source=label,
            require_device_local_producer=require_device_local_producer,
        )
    except RuntimeTelemetryHistoryError as exc:
        raise RuntimeIntelligenceLabHandoffError(
            f"runtime telemetry history seed is invalid for Lab handoff: {exc}"
        ) from exc


def _edgeenv_report_summary(regression_report: dict[str, Any]) -> dict[str, Any]:
    context = regression_report.get("runtime_telemetry_context")
    candidate_context = (
        context.get("candidate", {}) if isinstance(context, dict) else {}
    )
    history = context.get("history", {}) if isinstance(context, dict) else {}
    history_summary = history.get("summary", {}) if isinstance(history, dict) else {}
    history_seed_run_config_markers = _history_seed_run_config_markers(history)
    device_local_context_run_ids = _device_local_producer_context_run_ids(context)
    guard_alignment_run_ids = _producer_lineage_guard_alignment_run_ids(context)
    operation_risk_rollup_run_ids = _operation_risk_rollup_run_ids(context)
    task_event_rollup_run_ids = _task_event_rollup_run_ids(context)
    operation_timeline_summary_run_ids = _operation_timeline_summary_run_ids(
        context
    )
    policy_pressure_summary_run_ids = _policy_pressure_summary_run_ids(context)
    stale_drop_summary_run_ids = _stale_drop_summary_run_ids(context)
    fixture_matrix_summary = _fixture_matrix_summary(
        regression_report.get("fixture_matrix_context")
    )
    duration_traceability = _duration_traceability_summary(context)
    summary = {
        "baseline_run_id": regression_report.get("baseline_run_id"),
        "candidate_run_id": regression_report.get("candidate_run_id"),
        "comparable": regression_report.get("comparable"),
        "mode": regression_report.get("mode"),
        "regression_detected": regression_report.get("regression_detected"),
        "regression_type": regression_report.get("regression_type"),
        "severity": regression_report.get("severity"),
        "runtime_telemetry_context_present": isinstance(context, dict),
        "history_seed_runs": history_summary.get("history_seed_runs")
        if isinstance(history_summary, dict)
        else None,
        "history_seed_run_config_runs": history_summary.get(
            "history_seed_run_config_runs"
        )
        if isinstance(history_summary, dict)
        else None,
        "history_seed_run_config_marker_fields": list(RUN_CONFIG_MARKER_FIELDS),
        "history_seed_run_config_markers": history_seed_run_config_markers,
        "orchestrator_context_present": (
            isinstance(candidate_context, dict)
            and isinstance(
                candidate_context.get("orchestrator_operation_context"),
                dict,
            )
        ),
        "device_local_producer_context_present": bool(
            device_local_context_run_ids
        ),
        "device_local_producer_context_run_ids": device_local_context_run_ids,
        "producer_lineage_guard_alignment_present": bool(guard_alignment_run_ids),
        "producer_lineage_guard_alignment_run_ids": guard_alignment_run_ids,
        "orchestrator_operation_risk_rollup_present": bool(
            operation_risk_rollup_run_ids
        ),
        "orchestrator_operation_risk_rollup_run_ids": (
            operation_risk_rollup_run_ids
        ),
        "orchestrator_task_event_rollup_present": bool(task_event_rollup_run_ids),
        "orchestrator_task_event_rollup_run_ids": task_event_rollup_run_ids,
        "orchestrator_operation_timeline_summary_present": bool(
            operation_timeline_summary_run_ids
        ),
        "orchestrator_operation_timeline_summary_run_ids": (
            operation_timeline_summary_run_ids
        ),
        "orchestrator_policy_pressure_summary_present": bool(
            policy_pressure_summary_run_ids
        ),
        "orchestrator_policy_pressure_summary_run_ids": (
            policy_pressure_summary_run_ids
        ),
        "orchestrator_stale_drop_summary_present": bool(
            stale_drop_summary_run_ids
        ),
        "orchestrator_stale_drop_summary_run_ids": stale_drop_summary_run_ids,
        "duration_traceability_present": bool(
            duration_traceability["run_ids"]
        ),
        "duration_traceability_run_ids": duration_traceability["run_ids"],
        "duration_sources": duration_traceability["sources"],
        "duration_scope_labels": duration_traceability["scope_labels"],
    }
    summary["fixture_matrix_context_present"] = bool(fixture_matrix_summary)
    summary.update(fixture_matrix_summary)
    return summary


def _fixture_matrix_summary(context: Any) -> dict[str, Any]:
    if not isinstance(context, dict):
        return {}
    required_roles = _string_list(context.get("required_roles"))
    covered_roles = _string_list(context.get("covered_roles"))
    covered_modes = _string_list(context.get("covered_modes"))
    boundaries = context.get("boundaries")
    if not isinstance(boundaries, dict):
        boundaries = {}
    return {
        "fixture_matrix_schema_version": context.get("schema_version"),
        "fixture_matrix_owner": context.get("owner"),
        "fixture_matrix_required_role_count": context.get(
            "required_role_count",
            len(required_roles),
        ),
        "fixture_matrix_covered_role_count": context.get(
            "covered_role_count",
            len(covered_roles),
        ),
        "fixture_matrix_covered_modes": covered_modes,
        "fixture_matrix_comparability_first": boundaries.get(
            "comparability_first"
        ),
        "fixture_matrix_not_a_deployment_decision": boundaries.get(
            "not_a_deployment_decision"
        ),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _duration_traceability_summary(context: Any) -> dict[str, list[str]]:
    summary: dict[str, list[str]] = {
        "run_ids": [],
        "sources": [],
        "scope_labels": [],
    }
    if not isinstance(context, dict):
        return summary

    def append_unique(field: str, value: Any) -> None:
        if isinstance(value, str) and value and value not in summary[field]:
            summary[field].append(value)

    def inspect_run_context(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        source = run_context.get("duration_source")
        scope_label = run_context.get("duration_scope_label")
        if source is None and scope_label is None:
            return
        append_unique("run_ids", run_context.get("run_id"))
        append_unique("sources", source)
        append_unique("scope_labels", scope_label)

    inspect_run_context(context.get("baseline"))
    inspect_run_context(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                inspect_run_context(entry)
    return summary


def _history_seed_run_config_markers(history: Any) -> list[dict[str, Any]]:
    if not isinstance(history, dict):
        return []
    markers: list[dict[str, Any]] = []
    for entry in history.get("runs", []):
        if not isinstance(entry, dict):
            continue
        history_seed = entry.get("runtime_telemetry_history_seed")
        if not isinstance(history_seed, dict):
            continue
        run_config = history_seed.get("run_config")
        if not isinstance(run_config, dict):
            continue
        marker: dict[str, Any] = {"run_id": entry.get("run_id")}
        shape_label = _run_config_shape_label(run_config)
        if shape_label:
            marker["shape"] = shape_label
        for field in RUN_CONFIG_MARKER_FIELDS:
            if field in run_config:
                marker[field] = run_config.get(field)
        markers.append(marker)
    return markers


def _run_config_shape_label(run_config: dict[str, Any]) -> str:
    batch = run_config.get("batch")
    height = run_config.get("height")
    width = run_config.get("width")
    if batch is None and height is None and width is None:
        return ""
    return f"{batch or '-'}x{height or '-'}x{width or '-'}"


def _requires_device_local_producer(history: dict[str, Any]) -> bool:
    summary = history.get("summary", {})
    orchestrator_feed_runs = (
        summary.get("orchestrator_feed_runs") if isinstance(summary, dict) else None
    )
    if (
        isinstance(orchestrator_feed_runs, (int, float))
        and not isinstance(orchestrator_feed_runs, bool)
        and orchestrator_feed_runs > 0
    ):
        return True
    for entry in history.get("runs", []):
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("orchestrator_operation_context"), dict)
        ):
            return True
    for entry in history.get("missing_telemetry", []):
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("orchestrator_operation_context"), dict)
        ):
            return True
    return False


def _device_local_producer_context_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []
    for run_context in (context.get("baseline"), context.get("candidate")):
        if not isinstance(run_context, dict):
            continue
        operation_context = run_context.get("orchestrator_operation_context")
        if _has_device_local_producer_context(operation_context):
            run_id = run_context.get("run_id")
            if isinstance(run_id, str) and run_id and run_id not in run_ids:
                run_ids.append(run_id)
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                if not isinstance(entry, dict):
                    continue
                operation_context = entry.get("orchestrator_operation_context")
                if _has_device_local_producer_context(operation_context):
                    run_id = entry.get("run_id")
                    if isinstance(run_id, str) and run_id and run_id not in run_ids:
                        run_ids.append(run_id)
    return run_ids


def _producer_lineage_guard_alignment_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_aligned(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_producer_lineage_guard_alignment(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_aligned(context.get("baseline"))
    append_if_aligned(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_aligned(entry)
    return run_ids


def _task_event_rollup_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_present(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_task_event_rollup(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_present(context.get("baseline"))
    append_if_present(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_present(entry)
    return run_ids


def _operation_risk_rollup_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_present(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_operation_risk_rollup(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_present(context.get("baseline"))
    append_if_present(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_present(entry)
    return run_ids


def _operation_timeline_summary_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_present(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_operation_timeline_summary(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_present(context.get("baseline"))
    append_if_present(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_present(entry)
    return run_ids


def _stale_drop_summary_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_present(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_stale_drop_summary(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_present(context.get("baseline"))
    append_if_present(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_present(entry)
    return run_ids


def _policy_pressure_summary_run_ids(context: Any) -> list[str]:
    if not isinstance(context, dict):
        return []
    run_ids: list[str] = []

    def append_if_present(run_context: Any) -> None:
        if not isinstance(run_context, dict):
            return
        operation_context = run_context.get("orchestrator_operation_context")
        if not _has_policy_pressure_summary(operation_context):
            return
        run_id = run_context.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)

    append_if_present(context.get("baseline"))
    append_if_present(context.get("candidate"))
    history = context.get("history")
    if isinstance(history, dict):
        for section in ("runs", "missing_telemetry"):
            for entry in history.get(section, []):
                append_if_present(entry)
    return run_ids


def _has_task_event_rollup(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    candidate_context = operation_context.get("candidate_context")
    if not isinstance(candidate_context, dict):
        return False
    operation = candidate_context.get("operation")
    if not isinstance(operation, dict):
        return False
    summary = operation.get("runtime_task_event_summary")
    return isinstance(summary, dict) and bool(summary)


def _has_operation_risk_rollup(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    if isinstance(operation_context.get("operation_risk_rollup"), dict):
        return True
    operation = _candidate_operation_context(operation_context)
    return isinstance(operation.get("operation_risk_rollup"), dict)


def _has_operation_timeline_summary(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    operation = _candidate_operation_context(operation_context)
    return isinstance(operation.get("operation_timeline_summary"), dict)


def _has_policy_pressure_summary(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    operation = _candidate_operation_context(operation_context)
    if isinstance(operation.get("policy_pressure_summary"), dict):
        return True
    timeline = operation.get("operation_timeline_summary")
    return (
        isinstance(timeline, dict)
        and isinstance(timeline.get("policy_pressure"), dict)
    )


def _has_stale_drop_summary(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    operation = _candidate_operation_context(operation_context)
    if isinstance(operation.get("stale_drop_summary"), dict):
        return True
    timeline = operation.get("operation_timeline_summary")
    return (
        isinstance(timeline, dict)
        and isinstance(timeline.get("stale_drop"), dict)
    )


def _candidate_operation_context(operation_context: dict[str, Any]) -> dict[str, Any]:
    candidate_context = operation_context.get("candidate_context")
    if not isinstance(candidate_context, dict):
        return {}
    operation = candidate_context.get("operation")
    return operation if isinstance(operation, dict) else {}


def _has_producer_lineage_guard_alignment(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    alignment = operation_context.get("downstream_guard_alignment")
    return (
        isinstance(alignment, dict)
        and alignment.get("producer_lineage_evidence_type")
        == ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    )


def _has_device_local_producer_context(operation_context: Any) -> bool:
    if not isinstance(operation_context, dict):
        return False
    candidate_context = operation_context.get("candidate_context")
    if not isinstance(candidate_context, dict):
        return False
    producer = candidate_context.get("producer")
    if not isinstance(producer, dict):
        return False
    sources = producer.get("device_local_producer_sources")
    return isinstance(sources, list) and bool(sources)


def _validate_device_local_producer_lineage(
    candidate_context: Any,
    *,
    label: str,
    source: Path,
) -> None:
    if not isinstance(candidate_context, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"{label} must be an object: {source}"
        )
    producer = candidate_context.get("producer")
    if not isinstance(producer, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"{label}.producer is required for device-local lineage: {source}"
        )
    for field in ("producer_sources", "device_local_producer_sources"):
        values = producer.get(field)
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(item, str) and item for item in values)
        ):
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.{field} must be a non-empty string list: "
                f"{source}"
            )
    producer_sources = producer.get("producer_sources")
    device_local_sources = producer.get("device_local_producer_sources")
    if isinstance(producer_sources, list) and isinstance(device_local_sources, list):
        missing_from_sources = sorted(set(device_local_sources) - set(producer_sources))
        if missing_from_sources:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.device_local_producer_sources must also "
                "appear in producer_sources: "
                f"{', '.join(missing_from_sources)}: {source}"
            )
    sources_by_task = producer.get("producer_sources_by_task")
    if not isinstance(sources_by_task, dict) or not sources_by_task:
        raise RuntimeIntelligenceLabHandoffError(
            f"{label}.producer.producer_sources_by_task must be a non-empty "
            f"object: {source}"
        )
    task_sources: set[str] = set()
    for task_name, sources in sources_by_task.items():
        if not isinstance(task_name, str) or not task_name:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.producer_sources_by_task keys must be "
                f"non-empty strings: {source}"
            )
        if (
            not isinstance(sources, list)
            or not sources
            or not all(isinstance(item, str) and item for item in sources)
        ):
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.producer_sources_by_task.{task_name} "
                f"must be a non-empty string list: {source}"
            )
        task_sources.update(sources)
    if isinstance(device_local_sources, list):
        missing_from_task_sources = sorted(set(device_local_sources) - task_sources)
        if missing_from_task_sources:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.device_local_producer_sources must also "
                "appear in producer_sources_by_task: "
                f"{', '.join(missing_from_task_sources)}: {source}"
            )
    stage_by_task = producer.get("producer_stage_by_task")
    if not isinstance(stage_by_task, dict) or not stage_by_task:
        raise RuntimeIntelligenceLabHandoffError(
            f"{label}.producer.producer_stage_by_task must be a non-empty "
            f"object: {source}"
        )
    for task_name, stage in stage_by_task.items():
        if not isinstance(task_name, str) or not task_name:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.producer_stage_by_task keys must be "
                f"non-empty strings: {source}"
            )
        if not isinstance(stage, str) or not stage:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.producer_stage_by_task.{task_name} "
                f"must be a non-empty string: {source}"
            )
    if (
        producer.get("operation_context_role")
        != ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE
    ):
        raise RuntimeIntelligenceLabHandoffError(
            f"{label}.producer.operation_context_role must be "
            f"{ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE}: {source}"
        )
    for field in (
        "producer_event_count",
        "device_local_event_count",
        "device_local_task_count",
    ):
        value = producer.get(field)
        if type(value) is not int or value <= 0:
            raise RuntimeIntelligenceLabHandoffError(
                f"{label}.producer.{field} must be a positive integer: {source}"
            )


def _validate_orchestrator_stale_drop_context(
    operation_context: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    operation = _candidate_operation_context(operation_context)
    _validate_orchestrator_stale_drop_summary(
        operation.get("stale_drop_summary"),
        regression_path=regression_path,
    )
    timeline = operation.get("operation_timeline_summary")
    if isinstance(timeline, dict):
        _validate_orchestrator_stale_drop_summary(
            timeline.get("stale_drop"),
            regression_path=regression_path,
        )


def _validate_orchestrator_policy_pressure_context(
    operation_context: dict[str, Any],
    *,
    regression_path: Path,
) -> None:
    operation = _candidate_operation_context(operation_context)
    _validate_orchestrator_policy_pressure_summary(
        operation.get("policy_pressure_summary"),
        regression_path=regression_path,
    )
    timeline = operation.get("operation_timeline_summary")
    if isinstance(timeline, dict):
        _validate_orchestrator_policy_pressure_summary(
            timeline.get("policy_pressure"),
            regression_path=regression_path,
        )


def _validate_orchestrator_policy_pressure_summary(
    value: Any,
    *,
    regression_path: Path,
) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"policy_pressure_summary must be an object: {regression_path}"
        )
    expected_pairs = {
        "schema_version": ORCHESTRATOR_POLICY_PRESSURE_SUMMARY_SCHEMA_VERSION,
        "role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
    }
    for key, expected in expected_pairs.items():
        if value.get(key) != expected:
            raise RuntimeIntelligenceLabHandoffError(
                f"policy_pressure_summary.{key} must be {expected}: "
                f"{regression_path}"
            )
    if value.get("not_a_deployment_decision") is not True:
        raise RuntimeIntelligenceLabHandoffError(
            f"policy_pressure_summary.not_a_deployment_decision must be true: "
            f"{regression_path}"
        )
    decision_count = value.get("decision_count")
    if type(decision_count) is not int or decision_count < 0:
        raise RuntimeIntelligenceLabHandoffError(
            f"policy_pressure_summary.decision_count must be a non-negative "
            f"integer: {regression_path}"
        )
    for field in ("decision_reason_counts",):
        field_value = value.get(field)
        if field_value is not None and not isinstance(field_value, dict):
            raise RuntimeIntelligenceLabHandoffError(
                f"policy_pressure_summary.{field} must be an object when "
                f"present: {regression_path}"
            )
    for field in (
        "limited_tasks",
        "protected_tasks",
        "fallback_tasks",
        "pressure_markers",
    ):
        field_value = value.get(field)
        if field_value is not None and (
            not isinstance(field_value, list)
            or not all(isinstance(item, str) for item in field_value)
        ):
            raise RuntimeIntelligenceLabHandoffError(
                f"policy_pressure_summary.{field} must be a string list when "
                f"present: {regression_path}"
            )


def _validate_orchestrator_stale_drop_summary(
    value: Any,
    *,
    regression_path: Path,
) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise RuntimeIntelligenceLabHandoffError(
            f"stale_drop_summary must be an object: {regression_path}"
        )
    expected_pairs = {
        "schema_version": ORCHESTRATOR_STALE_DROP_SUMMARY_SCHEMA_VERSION,
        "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
    }
    for key, expected in expected_pairs.items():
        if value.get(key) != expected:
            raise RuntimeIntelligenceLabHandoffError(
                f"stale_drop_summary.{key} must be {expected}: "
                f"{regression_path}"
            )
    if value.get("not_a_deployment_decision") is not True:
        raise RuntimeIntelligenceLabHandoffError(
            f"stale_drop_summary.not_a_deployment_decision must be true: "
            f"{regression_path}"
        )
    for field in ("stale_drop_count", "total_drop_count"):
        field_value = value.get(field)
        if type(field_value) is not int or field_value < 0:
            raise RuntimeIntelligenceLabHandoffError(
                f"stale_drop_summary.{field} must be a non-negative integer: "
                f"{regression_path}"
            )
    for field in ("stale_drop_reasons", "task_counts"):
        field_value = value.get(field)
        if field_value is not None and not isinstance(field_value, dict):
            raise RuntimeIntelligenceLabHandoffError(
                f"stale_drop_summary.{field} must be an object when present: "
                f"{regression_path}"
            )
    tasks = value.get("tasks_with_stale_drop")
    if tasks is not None and (
        not isinstance(tasks, list)
        or not all(isinstance(item, str) for item in tasks)
    ):
        raise RuntimeIntelligenceLabHandoffError(
            "stale_drop_summary.tasks_with_stale_drop must be a string list "
            f"when present: {regression_path}"
        )


def _lab_bundle_alignment(files: dict[str, str]) -> dict[str, Any]:
    produced_file_keys = tuple(sorted(files))
    required_file_keys = (
        "baseline_result",
        "candidate_result",
        "edgeenv_regression_report",
        *LAB_BUNDLE_EXTERNAL_FILE_KEYS,
    )
    return {
        "bundle_schema_version": LAB_RUNTIME_INTELLIGENCE_BUNDLE_SCHEMA_VERSION,
        "required_file_keys": list(required_file_keys),
        "edgeenv_produced_file_keys": list(produced_file_keys),
        "external_file_keys": list(LAB_BUNDLE_EXTERNAL_FILE_KEYS),
        "source_repositories": dict(LAB_BUNDLE_SOURCE_REPOSITORIES),
        "artifact_roles": dict(LAB_BUNDLE_ARTIFACT_ROLES),
        "producer_contracts": dict(LAB_BUNDLE_PRODUCER_CONTRACTS),
        "external_aiguard_required_evidence_types": list(
            LAB_BUNDLE_EXTERNAL_AIGUARD_REQUIRED_EVIDENCE_TYPES
        ),
        "optional_aiguard_evidence_types": list(
            LAB_BUNDLE_OPTIONAL_AIGUARD_EVIDENCE_TYPES
        ),
        "optional_aiguard_source_traceability": (
            _optional_aiguard_source_traceability()
        ),
        "expected_report_markers": list(LAB_BUNDLE_EXPECTED_REPORT_MARKERS),
        "external_aiguard_alignment_gate": {
            "declared_by": "edgeenv",
            "guard_analysis_file_key": "aiguard_guard_analysis",
            "validated_by": [
                "inferedge-aiguard check-edgeenv-handoff-alignment",
                "inferedgelab runtime-intelligence bundle manifest gate",
            ],
            "edgeenv_does_not_generate_guard_analysis": True,
            "lab_is_final_decision_owner": True,
        },
        "boundary_flags": {
            "orchestrator_context_is_verdict": False,
            "orchestrator_context_is_comparability_gate": False,
            "aiguard_guard_analysis_is_external": True,
            "aiguard_is_final_decision_owner": False,
            "edgeenv_does_not_generate_guard_analysis": True,
            "lab_is_final_decision_owner": True,
            "production_observability_platform": False,
        },
    }


def _optional_aiguard_source_traceability() -> dict[str, Any]:
    return {
        "context_role": LAB_BUNDLE_OPTIONAL_AIGUARD_SOURCE_TRACEABILITY_CONTEXT_ROLE,
        "edgeenv_does_not_generate_guard_analysis": True,
        "lab_is_final_decision_owner": True,
        "optional_present_source_artifact": {
            "repository": "InferEdgeAIGuard",
            "path": (
                "examples/runtime_intelligence/"
                "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
            ),
            "schema_version": AIGUARD_DIAGNOSIS_SCHEMA_VERSION,
            "role": "aiguard-optional-stale-drop-full-evidence-source",
            "context_role": "read_only_cross_repo_traceability",
            "reproduction_command": list(
                LAB_BUNDLE_OPTIONAL_AIGUARD_STALE_DROP_REPRODUCTION_COMMAND
            ),
        },
    }
