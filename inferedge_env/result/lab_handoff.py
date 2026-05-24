from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
    ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
    ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
    ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
    ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS,
    ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION,
    RuntimeTelemetryHistoryError,
    RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
    RUNTIME_TELEMETRY_HISTORY_SEED_SCHEMA_VERSION,
    validate_runtime_telemetry_history,
)


RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION = (
    "edgeenv.runtime-intelligence-lab-handoff.v1"
)

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

BOUNDARIES = {
    "orchestrator_context_is_verdict": False,
    "orchestrator_context_is_comparability_gate": False,
    "edgeenv_is_final_decision_owner": False,
    "lab_is_final_decision_owner": True,
    "production_observability_platform": False,
}


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
    baseline_run_id = baseline_result.get("run_id")
    candidate_run_id = candidate_result.get("run_id")
    if not isinstance(baseline_run_id, str) or not baseline_run_id:
        raise RuntimeIntelligenceLabHandoffError(
            "baseline result must include a non-empty run_id"
        )
    if not isinstance(candidate_run_id, str) or not candidate_run_id:
        raise RuntimeIntelligenceLabHandoffError(
            "candidate result must include a non-empty run_id"
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


def _validate_telemetry_history(
    history_payload: dict[str, Any],
    *,
    history_path: Path,
) -> None:
    try:
        validate_runtime_telemetry_history(history_payload, source=history_path)
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
    try:
        validate_runtime_telemetry_history(payload, source=label)
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
    return {
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
        "orchestrator_context_present": (
            isinstance(candidate_context, dict)
            and isinstance(
                candidate_context.get("orchestrator_operation_context"),
                dict,
            )
        ),
    }
