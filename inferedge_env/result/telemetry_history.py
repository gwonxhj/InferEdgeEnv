from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inferedge_env.registry.db import RunRegistry
from inferedge_env.registry.models import RegistryRecord
from inferedge_env.result.schema import RunResult
from inferedge_env.result.writer import load_result


RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION = "edgeenv.runtime-telemetry-history.v1"
RUNTIME_TELEMETRY_HISTORY_SEED_SCHEMA_VERSION = (
    "inferedge-runtime-telemetry-history-seed-v1"
)
ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION = (
    "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1"
)
ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY = "InferEdgeOrchestrator"
ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE = (
    "orchestrator-supplemental-operation-context"
)
ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT = (
    ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION
)
ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH = "runtime_telemetry_context.candidate"
ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH = (
    "runtime_telemetry_context.history.telemetry_coverage"
)
ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER = "edgeenv"
ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE = "supplemental"
ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS = (
    "run_id",
    "telemetry_source",
    "operation",
    "resource",
)
ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES = (
    "runtime_queue_overload",
    "runtime_thermal_instability",
)
ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE = (
    "edgeenv_orchestrator_producer_lineage"
)
ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE = (
    "remote_dispatch_runtime_event_compact_summary"
)
ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY = "remote dispatch starter evidence only"
ORCHESTRATOR_OPERATION_RISK_SUMMARY_SCHEMA_VERSION = (
    "inferedge-entrypoint-operation-risk-summary-v1"
)
ORCHESTRATOR_OPERATION_RISK_SUMMARY_EVIDENCE_ROLE = "derived_navigation_context"
ORCHESTRATOR_OPERATION_RISK_ROLLUP_SCHEMA_VERSION = (
    "inferedge-orchestrator-operation-risk-rollup-v1"
)
ORCHESTRATOR_OPERATION_TIMELINE_SUMMARY_SCHEMA_VERSION = (
    "inferedge-orchestrator-operation-timeline-summary-v1"
)
ORCHESTRATOR_STALE_DROP_SUMMARY_SCHEMA_VERSION = (
    "inferedge-orchestrator-stale-drop-summary-v1"
)


class RuntimeTelemetryHistoryError(ValueError):
    """Raised when runtime telemetry history cannot be built safely."""


def build_runtime_telemetry_history(
    edgeenv_root: Path | str,
    *,
    run_ids: list[str] | None = None,
    generated_at: datetime | None = None,
    orchestrator_feeds: list[Path | str] | None = None,
) -> dict[str, Any]:
    root = Path(edgeenv_root)
    registry = RunRegistry(root / "runs.db")
    records = _select_records(registry, run_ids)
    generated = generated_at or datetime.now(timezone.utc)
    orchestrator_contexts = _load_orchestrator_feeds(orchestrator_feeds)
    _validate_orchestrator_feed_scope(orchestrator_contexts, records)

    entries: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for record in records:
        result = _load_record_result(record)
        if result.runtime_telemetry is None:
            missing_entry: dict[str, Any] = {
                "run_id": result.run_id,
                "reason": "runtime_telemetry_missing",
            }
            orchestrator_context = orchestrator_contexts.get(result.run_id)
            if orchestrator_context is not None:
                missing_entry["orchestrator_operation_context"] = (
                    orchestrator_context
                )
            missing.append(missing_entry)
            continue
        entries.append(
            _history_entry(
                result,
                orchestrator_context=orchestrator_contexts.get(result.run_id),
            )
        )

    entries.sort(
        key=lambda entry: (
            str(entry.get("telemetry_timestamp") or ""),
            _sequence_sort_value(entry.get("execution_sequence_id")),
            entry["created_at"],
            entry["run_id"],
        )
    )
    missing.sort(key=lambda item: item["run_id"])
    telemetry_coverage = _telemetry_coverage_summary(entries)
    return {
        "schema_version": RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION,
        "generated_at": generated.isoformat(),
        "source": {
            "edgeenv_root": str(root),
            "registry": str(root / "runs.db"),
        },
        "summary": {
            "requested_runs": len(run_ids) if run_ids is not None else None,
            "registered_runs": len(records),
            "telemetry_runs": len(entries),
            "history_seed_runs": _history_seed_run_count(entries),
            "history_seed_run_config_runs": _history_seed_run_config_count(
                entries
            ),
            "missing_telemetry_runs": len(missing),
            "orchestrator_feed_runs": len(orchestrator_contexts),
        },
        "telemetry_coverage": telemetry_coverage,
        "runs": entries,
        "missing_telemetry": missing,
        "notes": [
            "Runtime telemetry history is local replay evidence, not production monitoring.",
            "Missing telemetry is recorded as an evidence gap, not a failed benchmark run.",
            "Comparability-first regression analysis must still run before delta judgement.",
            "Orchestrator feed context is supplemental operation evidence, not a regression judgement.",
        ],
    }


def write_runtime_telemetry_history(
    edgeenv_root: Path | str,
    output_path: Path | str,
    *,
    run_ids: list[str] | None = None,
    orchestrator_feeds: list[Path | str] | None = None,
) -> dict[str, Any]:
    payload = build_runtime_telemetry_history(
        edgeenv_root,
        run_ids=run_ids,
        orchestrator_feeds=orchestrator_feeds,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def load_runtime_telemetry_history(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history not found: {source}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeTelemetryHistoryError(
            f"Invalid runtime telemetry history JSON: {source}"
        ) from exc
    validate_runtime_telemetry_history(payload, source=source)
    return payload


def validate_runtime_telemetry_history(
    payload: Any,
    *,
    source: Path | str | None = None,
    require_device_local_producer: bool = False,
) -> None:
    label = str(source) if source is not None else "runtime telemetry history"
    if not isinstance(payload, dict):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history must be a JSON object: {label}"
        )
    schema_version = payload.get("schema_version")
    if schema_version != RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION:
        raise RuntimeTelemetryHistoryError(
            "Unsupported runtime telemetry history schema: "
            f"{schema_version or '<missing>'}"
        )
    if not isinstance(payload.get("summary"), dict):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history summary must be an object: {label}"
        )
    if not isinstance(payload.get("runs"), list):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history runs must be a list: {label}"
        )
    if not isinstance(payload.get("missing_telemetry", []), list):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history missing_telemetry must be a list: {label}"
        )
    if "telemetry_coverage" in payload and not isinstance(
        payload.get("telemetry_coverage"),
        dict,
    ):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history telemetry_coverage must be an object: {label}"
        )
    for index, entry in enumerate(payload["runs"]):
        if not isinstance(entry, dict):
            raise RuntimeTelemetryHistoryError(
                f"Runtime telemetry history runs[{index}] must be an object: {label}"
            )
        if not isinstance(entry.get("run_id"), str) or not entry.get("run_id"):
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history "
                f"runs[{index}].run_id must be a string: {label}"
            )
        runtime_telemetry = entry.get("runtime_telemetry")
        if runtime_telemetry is not None and not isinstance(runtime_telemetry, dict):
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history "
                f"runs[{index}].runtime_telemetry must be an object: {label}"
            )
        history_seed = entry.get("runtime_telemetry_history_seed")
        if history_seed is not None:
            _validate_runtime_history_seed(
                history_seed,
                label=f"{label} runs[{index}].runtime_telemetry_history_seed",
            )
        orchestrator_context = entry.get("orchestrator_operation_context")
        if orchestrator_context is not None:
            if not isinstance(
                orchestrator_context,
                dict,
            ):
                raise RuntimeTelemetryHistoryError(
                    "Runtime telemetry history "
                    f"runs[{index}].orchestrator_operation_context must be an object: "
                    f"{label}"
                )
            _validate_preserved_orchestrator_context(
                orchestrator_context,
                label=(
                    "Runtime telemetry history "
                    f"runs[{index}].orchestrator_operation_context"
                ),
                require_device_local_producer=require_device_local_producer,
            )
    for index, item in enumerate(payload.get("missing_telemetry", [])):
        if not isinstance(item, dict):
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history "
                f"missing_telemetry[{index}] must be an object: {label}"
            )
        orchestrator_context = item.get("orchestrator_operation_context")
        if orchestrator_context is None:
            continue
        if not isinstance(orchestrator_context, dict):
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history "
                f"missing_telemetry[{index}].orchestrator_operation_context "
                f"must be an object: {label}"
            )
        _validate_preserved_orchestrator_context(
            orchestrator_context,
            label=(
                "Runtime telemetry history "
                f"missing_telemetry[{index}].orchestrator_operation_context"
            ),
            require_device_local_producer=require_device_local_producer,
        )
    if require_device_local_producer and not _has_orchestrator_context(payload):
        raise RuntimeTelemetryHistoryError(
            "Runtime telemetry history must include at least one "
            "orchestrator_operation_context when device-local producer lineage "
            "is required"
        )


def inspect_runtime_telemetry_history(
    payload: dict[str, Any],
    *,
    require_device_local_producer: bool = False,
) -> dict[str, Any]:
    validate_runtime_telemetry_history(
        payload,
        require_device_local_producer=require_device_local_producer,
    )
    runs = payload.get("runs", [])
    missing = payload.get("missing_telemetry", [])
    run_ids = [entry["run_id"] for entry in runs]
    missing_orchestrator_context_run_ids = [
        item["run_id"]
        for item in missing
        if isinstance(item, dict)
        and isinstance(item.get("run_id"), str)
        and isinstance(item.get("orchestrator_operation_context"), dict)
    ]
    device_local_producer_context_run_ids = _device_local_producer_context_run_ids(
        payload
    )
    producer_lineage_guard_alignment_run_ids = (
        _producer_lineage_guard_alignment_run_ids(payload)
    )
    operation_risk_summary_run_ids = _operation_risk_summary_run_ids(payload)
    operation_risk_rollup_run_ids = _operation_risk_rollup_run_ids(payload)
    operation_timeline_summary_run_ids = _operation_timeline_summary_run_ids(
        payload
    )
    stale_drop_summary_run_ids = _stale_drop_summary_run_ids(payload)
    timestamps = [
        entry.get("telemetry_timestamp")
        for entry in runs
        if entry.get("telemetry_timestamp") is not None
    ]
    sequence_ids = [entry.get("execution_sequence_id") for entry in runs]
    numeric_sequence_ids = [
        value for value in sequence_ids if isinstance(value, (int, float))
    ]
    telemetry_coverage = payload.get("telemetry_coverage")
    if not isinstance(telemetry_coverage, dict):
        telemetry_coverage = _telemetry_coverage_summary(runs)
    return {
        "schema_version": payload["schema_version"],
        "valid": True,
        "summary": payload["summary"],
        "source": payload.get("source", {}),
        "replay": {
            "run_ids": run_ids,
            "telemetry_fields": _telemetry_fields(runs),
            "telemetry_coverage": telemetry_coverage,
            "history_seed_run_ids": [
                entry["run_id"]
                for entry in runs
                if isinstance(entry.get("runtime_telemetry_history_seed"), dict)
            ],
            "history_seed_run_config_run_ids": [
                entry["run_id"]
                for entry in runs
                if _has_runtime_history_seed_run_config(entry)
            ],
            "orchestrator_context_run_ids": [
                entry["run_id"]
                for entry in runs
                if isinstance(entry.get("orchestrator_operation_context"), dict)
            ]
            + missing_orchestrator_context_run_ids,
            "missing_orchestrator_context_run_ids": (
                missing_orchestrator_context_run_ids
            ),
            "device_local_producer_context_run_ids": (
                device_local_producer_context_run_ids
            ),
            "producer_lineage_guard_alignment_run_ids": (
                producer_lineage_guard_alignment_run_ids
            ),
            "operation_risk_summary_run_ids": operation_risk_summary_run_ids,
            "operation_risk_rollup_run_ids": operation_risk_rollup_run_ids,
            "operation_timeline_summary_run_ids": (
                operation_timeline_summary_run_ids
            ),
            "stale_drop_summary_run_ids": stale_drop_summary_run_ids,
            "first_telemetry_timestamp": min(timestamps) if timestamps else None,
            "last_telemetry_timestamp": max(timestamps) if timestamps else None,
            "execution_sequence_ids": sequence_ids,
            "sequence_monotonic": _is_monotonic(numeric_sequence_ids)
            if numeric_sequence_ids
            else None,
            "evidence_gap_count": len(missing),
            "missing_run_ids": [
                item.get("run_id")
                for item in missing
                if isinstance(item, dict) and item.get("run_id")
            ],
        },
        "notes": [
            "Runtime telemetry history inspection is read-only replay evidence validation.",
            "It does not change comparability judgement or regression thresholds.",
            "It is not production monitoring, distributed tracing, or a cloud telemetry store.",
        ],
    }


def _has_orchestrator_context(payload: dict[str, Any]) -> bool:
    for entry in payload.get("runs", []):
        if isinstance(entry, dict) and isinstance(
            entry.get("orchestrator_operation_context"),
            dict,
        ):
            return True
    for item in payload.get("missing_telemetry", []):
        if isinstance(item, dict) and isinstance(
            item.get("orchestrator_operation_context"),
            dict,
        ):
            return True
    return False


def _device_local_producer_context_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_device_local_producer_context(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str) and run_id:
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_device_local_producer_context(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str) and run_id:
                run_ids.append(run_id)
    return run_ids


def _producer_lineage_guard_alignment_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_producer_lineage_guard_alignment(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_producer_lineage_guard_alignment(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    return run_ids


def _operation_risk_summary_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_operation_risk_summary(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_operation_risk_summary(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    return run_ids


def _has_operation_risk_summary(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("operation_risk_summary"), dict)
    )


def _operation_risk_rollup_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_operation_risk_rollup(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_operation_risk_rollup(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    return run_ids


def _operation_timeline_summary_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_operation_timeline_summary(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_operation_timeline_summary(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    return run_ids


def _stale_drop_summary_run_ids(payload: dict[str, Any]) -> list[str]:
    run_ids: list[str] = []
    for entry in payload.get("runs", []):
        if not isinstance(entry, dict):
            continue
        context = entry.get("orchestrator_operation_context")
        if _has_stale_drop_summary(context):
            run_id = entry.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    for item in payload.get("missing_telemetry", []):
        if not isinstance(item, dict):
            continue
        context = item.get("orchestrator_operation_context")
        if _has_stale_drop_summary(context):
            run_id = item.get("run_id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
    return run_ids


def _has_operation_risk_rollup(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if isinstance(value.get("operation_risk_rollup"), dict):
        return True
    operation = _candidate_operation_context(value)
    return isinstance(operation.get("operation_risk_rollup"), dict)


def _has_operation_timeline_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    operation = _candidate_operation_context(value)
    return isinstance(operation.get("operation_timeline_summary"), dict)


def _has_stale_drop_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    operation = _candidate_operation_context(value)
    if isinstance(operation.get("stale_drop_summary"), dict):
        return True
    timeline = operation.get("operation_timeline_summary")
    return (
        isinstance(timeline, dict)
        and isinstance(timeline.get("stale_drop"), dict)
    )


def _candidate_operation_context(value: dict[str, Any]) -> dict[str, Any]:
    candidate_context = value.get("candidate_context")
    if not isinstance(candidate_context, dict):
        return {}
    operation = candidate_context.get("operation")
    return operation if isinstance(operation, dict) else {}


def _has_producer_lineage_guard_alignment(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    alignment = value.get("downstream_guard_alignment")
    if not isinstance(alignment, dict):
        return False
    return (
        alignment.get("producer_lineage_evidence_type")
        == ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    )


def _has_device_local_producer_context(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    candidate_context = value.get("candidate_context")
    if not isinstance(candidate_context, dict):
        return False
    producer = candidate_context.get("producer")
    if not isinstance(producer, dict):
        return False
    sources = producer.get("device_local_producer_sources")
    return isinstance(sources, list) and bool(sources)


def _select_records(
    registry: RunRegistry,
    run_ids: list[str] | None,
) -> list[RegistryRecord]:
    if run_ids is None:
        return registry.list_runs()
    records: list[RegistryRecord] = []
    seen: set[str] = set()
    for run_id in run_ids:
        if run_id in seen:
            continue
        seen.add(run_id)
        try:
            records.append(registry.show(run_id))
        except KeyError as exc:
            raise RuntimeTelemetryHistoryError(str(exc)) from exc
    return records


def _load_record_result(record: RegistryRecord) -> RunResult:
    try:
        return load_result(record.result_path)
    except (OSError, ValueError) as exc:
        raise RuntimeTelemetryHistoryError(
            f"Invalid result artifact for run {record.run_id}: {record.result_path}"
        ) from exc


def _history_entry(
    result: RunResult,
    *,
    orchestrator_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    telemetry = result.runtime_telemetry
    if telemetry is None:
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry missing for run: {result.run_id}"
        )
    entry = {
        "run_id": result.run_id,
        "created_at": result.created_at.isoformat(),
        "telemetry_timestamp": telemetry.get("telemetry_timestamp"),
        "execution_sequence_id": telemetry.get("execution_sequence_id"),
        "target": result.target.model_dump(mode="json"),
        "model": result.model.model_dump(mode="json"),
        "runtime": result.runtime.model_dump(mode="json"),
        "protocol": result.protocol.model_dump(mode="json"),
        "metrics": result.metrics.model_dump(mode="json"),
        "runtime_telemetry": telemetry,
    }
    history_seed = _runtime_telemetry_history_seed(telemetry, run_id=result.run_id)
    if history_seed is not None:
        entry["runtime_telemetry_history_seed"] = history_seed
    if orchestrator_context is not None:
        entry["orchestrator_operation_context"] = orchestrator_context
    return entry


def _load_orchestrator_feeds(
    orchestrator_feeds: list[Path | str] | None,
) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for feed_path in orchestrator_feeds or []:
        context = _load_orchestrator_feed(feed_path)
        run_id = context["run_id"]
        if run_id in contexts:
            raise RuntimeTelemetryHistoryError(
                f"Duplicate Orchestrator telemetry feed for run: {run_id}"
            )
        contexts[run_id] = context
    return contexts


def _load_orchestrator_feed(feed_path: Path | str) -> dict[str, Any]:
    source = Path(feed_path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeTelemetryHistoryError(
            f"Orchestrator telemetry feed not found: {source}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeTelemetryHistoryError(
            f"Invalid Orchestrator telemetry feed JSON: {source}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeTelemetryHistoryError(
            f"Orchestrator telemetry feed must be a JSON object: {source}"
        )
    schema_version = payload.get("schema_version")
    if schema_version != ORCHESTRATOR_TELEMETRY_FEED_SCHEMA_VERSION:
        raise RuntimeTelemetryHistoryError(
            "Unsupported Orchestrator telemetry feed schema: "
            f"{schema_version or '<missing>'}"
        )
    candidate_context = payload.get("candidate_context")
    if not isinstance(candidate_context, dict):
        raise RuntimeTelemetryHistoryError(
            f"Orchestrator telemetry feed candidate_context must be an object: {source}"
        )
    run_id = payload.get("run_id") or candidate_context.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeTelemetryHistoryError(
            f"Orchestrator telemetry feed run_id must be a string: {source}"
        )
    if payload.get("not_a_regression_judgement") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed must declare "
            "not_a_regression_judgement=true"
        )
    if payload.get("not_a_comparability_gate") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed must declare not_a_comparability_gate=true"
        )
    _validate_orchestrator_producer_markers(payload, source)
    mapping_hint = _validate_orchestrator_mapping_hint(
        payload.get("edgeenv_mapping_hint", {}),
        candidate_context=candidate_context,
        source=source,
    )
    downstream_guard_alignment = _validate_orchestrator_downstream_guard_alignment(
        payload.get("downstream_guard_alignment"),
        candidate_context=candidate_context,
        source=source,
    )
    remote_runtime_event_summary = _validate_orchestrator_remote_event_summary(
        payload.get("remote_runtime_event_summary"),
        source=source,
    )
    operation_risk_summary = _validate_orchestrator_operation_risk_summary(
        payload.get("operation_risk_summary"),
        source=source,
    )
    operation_risk_rollup = _validate_orchestrator_operation_risk_rollup(
        payload.get("operation_risk_rollup"),
        source=source,
    )
    _validate_orchestrator_candidate_operation_context(
        candidate_context,
        source=source,
    )
    preserved_context = {
        "schema_version": schema_version,
        "role": payload.get("role"),
        "source_repository": payload.get("source_repository"),
        "artifact_role": payload.get("artifact_role"),
        "producer_contract": payload.get("producer_contract"),
        "source": payload.get("source"),
        "run_id": run_id,
        "not_a_regression_judgement": True,
        "not_a_comparability_gate": True,
        "decision_owner": payload.get("decision_owner"),
        "regression_owner": payload.get("regression_owner"),
        "candidate_context": deepcopy(candidate_context),
        "edgeenv_mapping_hint": mapping_hint,
    }
    if downstream_guard_alignment is not None:
        preserved_context["downstream_guard_alignment"] = (
            downstream_guard_alignment
        )
    if remote_runtime_event_summary is not None:
        preserved_context["remote_runtime_event_summary"] = (
            remote_runtime_event_summary
        )
    if operation_risk_summary is not None:
        preserved_context["operation_risk_summary"] = operation_risk_summary
    if operation_risk_rollup is not None:
        preserved_context["operation_risk_rollup"] = operation_risk_rollup
    return preserved_context


def _validate_orchestrator_producer_markers(
    payload: dict[str, Any],
    source: Path,
) -> None:
    expected_pairs = {
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    }
    for key, expected in expected_pairs.items():
        if payload.get(key) != expected:
            raise RuntimeTelemetryHistoryError(
                f"Orchestrator telemetry feed {key} must be {expected}: {source}"
            )


def _validate_orchestrator_context_markers(
    context: dict[str, Any],
    *,
    label: str,
) -> None:
    expected_pairs = {
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    }
    for key, expected in expected_pairs.items():
        if context.get(key) != expected:
            raise RuntimeTelemetryHistoryError(f"{label}.{key} must be {expected}")


def _validate_preserved_orchestrator_context(
    context: dict[str, Any],
    *,
    label: str,
    require_device_local_producer: bool = False,
) -> None:
    _validate_orchestrator_context_markers(context, label=label)
    candidate_context = context.get("candidate_context")
    if not isinstance(candidate_context, dict):
        raise RuntimeTelemetryHistoryError(
            f"{label}.candidate_context must be an object"
        )
    _validate_orchestrator_mapping_hint(
        context.get("edgeenv_mapping_hint", {}),
        candidate_context=candidate_context,
        source=Path(label),
    )
    _validate_orchestrator_downstream_guard_alignment(
        context.get("downstream_guard_alignment"),
        candidate_context=candidate_context,
        source=Path(label),
    )
    _validate_orchestrator_remote_event_summary(
        context.get("remote_runtime_event_summary"),
        source=Path(label),
    )
    _validate_orchestrator_operation_risk_summary(
        context.get("operation_risk_summary"),
        source=Path(label),
    )
    _validate_orchestrator_operation_risk_rollup(
        context.get("operation_risk_rollup"),
        source=Path(label),
    )
    _validate_orchestrator_candidate_operation_context(
        candidate_context,
        source=Path(label),
    )
    _validate_orchestrator_producer_context(
        candidate_context.get("producer"),
        source=Path(label),
        require_device_local_producer=require_device_local_producer,
    )


def _validate_orchestrator_mapping_hint(
    value: Any,
    *,
    candidate_context: dict[str, Any],
    source: Path,
) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            f"Orchestrator telemetry feed edgeenv_mapping_hint must be an object: {source}"
        )
    mapping_hint = deepcopy(value)
    _validate_optional_mapping_value(
        mapping_hint,
        "copy_candidate_context_to",
        ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
        source,
    )
    _validate_optional_mapping_value(
        mapping_hint,
        "operation_context_role",
        ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        source,
    )
    _validate_optional_mapping_value(
        mapping_hint,
        "coverage_summary_owner",
        ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
        source,
    )
    _validate_optional_mapping_value(
        mapping_hint,
        "coverage_summary_path",
        ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
        source,
    )
    required_fields = mapping_hint.get("candidate_context_required_fields")
    if required_fields is not None:
        if not isinstance(required_fields, list) or not all(
            isinstance(item, str) for item in required_fields
        ):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed "
                f"edgeenv_mapping_hint.candidate_context_required_fields must be "
                f"a string list: {source}"
            )
        missing_required = [
            field
            for field in ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS
            if field not in required_fields
        ]
        if missing_required:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed "
                "edgeenv_mapping_hint.candidate_context_required_fields must "
                f"include {', '.join(missing_required)}: {source}"
            )
        missing_context = [
            field
            for field in ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS
            if field not in candidate_context
        ]
        if missing_context:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context must include "
                f"{', '.join(missing_context)} when declared as required: {source}"
            )
    evidence_candidates = mapping_hint.get("aiguard_evidence_candidates")
    if evidence_candidates is not None:
        if not isinstance(evidence_candidates, list) or not all(
            isinstance(item, str) for item in evidence_candidates
        ):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed "
                "edgeenv_mapping_hint.aiguard_evidence_candidates must be "
                f"a string list: {source}"
            )
        missing_candidates = [
            candidate
            for candidate in ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            if candidate not in evidence_candidates
        ]
        if missing_candidates:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed "
                "edgeenv_mapping_hint.aiguard_evidence_candidates must include "
                f"{', '.join(missing_candidates)}: {source}"
            )
    _validate_orchestrator_producer_context(
        candidate_context.get("producer"),
        source=source,
    )
    return mapping_hint


def _validate_orchestrator_downstream_guard_alignment(
    value: Any,
    *,
    candidate_context: dict[str, Any],
    source: Path,
) -> dict[str, Any] | None:
    producer_context = candidate_context.get("producer")
    require_alignment = isinstance(producer_context, dict)
    if value is None:
        if require_alignment:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed downstream_guard_alignment is "
                "required when candidate_context.producer is present: "
                f"{source}"
            )
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment must be "
            f"an object: {source}"
        )
    alignment = deepcopy(value)
    if alignment.get("declared_by") != "orchestrator":
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment.declared_by "
            f"must be orchestrator: {source}"
        )
    if (
        alignment.get("producer_lineage_evidence_type")
        != ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment."
            "producer_lineage_evidence_type must be "
            f"{ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE}: {source}"
        )
    operation_candidates = alignment.get("operation_evidence_candidates")
    if not isinstance(operation_candidates, list) or not all(
        isinstance(item, str) for item in operation_candidates
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment."
            f"operation_evidence_candidates must be a string list: {source}"
        )
    missing_candidates = [
        candidate
        for candidate in ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
        if candidate not in operation_candidates
    ]
    if missing_candidates:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment."
            "operation_evidence_candidates must include "
            f"{', '.join(missing_candidates)}: {source}"
        )
    if alignment.get("orchestrator_is_final_decision_owner") is not False:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment."
            "orchestrator_is_final_decision_owner must be false: "
            f"{source}"
        )
    if alignment.get("lab_is_final_decision_owner") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed downstream_guard_alignment."
            f"lab_is_final_decision_owner must be true: {source}"
        )
    return alignment


def _validate_orchestrator_remote_event_summary(
    value: Any,
    *,
    source: Path,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed remote_runtime_event_summary must be "
            f"an object: {source}"
        )
    summary = deepcopy(value)
    if summary.get("evidence_role") != ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed remote_runtime_event_summary."
            f"evidence_role must be {ORCHESTRATOR_REMOTE_RUNTIME_EVENT_SUMMARY_ROLE}: "
            f"{source}"
        )
    if summary.get("operation_boundary") != ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed remote_runtime_event_summary."
            f"operation_boundary must be {ORCHESTRATOR_REMOTE_OPERATION_BOUNDARY}: "
            f"{source}"
        )
    if summary.get("production_remote_execution") is not False:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed remote_runtime_event_summary."
            f"production_remote_execution must be false: {source}"
        )
    return summary


def _validate_orchestrator_operation_risk_summary(
    value: Any,
    *,
    source: Path,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_summary must be "
            f"an object: {source}"
        )
    summary = deepcopy(value)
    expected_pairs = {
        "schema_version": ORCHESTRATOR_OPERATION_RISK_SUMMARY_SCHEMA_VERSION,
        "evidence_role": ORCHESTRATOR_OPERATION_RISK_SUMMARY_EVIDENCE_ROLE,
        "decision_owner": "lab",
        "scheduler_owner": "orchestrator",
    }
    for key, expected in expected_pairs.items():
        if summary.get(key) != expected:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_summary."
                f"{key} must be {expected}: {source}"
            )
    if summary.get("not_a_deployment_decision") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_summary."
            f"not_a_deployment_decision must be true: {source}"
        )
    for field in (
        "queue_pressure_reason",
        "max_pressure_task",
        "primary_health_reason",
    ):
        field_value = summary.get(field)
        if field_value is not None and not isinstance(field_value, str):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_summary."
                f"{field} must be a string when present: {source}"
            )
    degraded_worker_ids = summary.get("degraded_worker_ids")
    if degraded_worker_ids is not None and (
        not isinstance(degraded_worker_ids, list)
        or not all(isinstance(item, str) for item in degraded_worker_ids)
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_summary."
            f"degraded_worker_ids must be a string list when present: {source}"
        )
    for field in ("device_local_event_count", "producer_event_count"):
        field_value = summary.get(field)
        if field_value is None:
            continue
        if isinstance(field_value, bool) or not isinstance(field_value, (int, str)):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_summary."
                f"{field} must be an integer or string marker when present: {source}"
            )
        if isinstance(field_value, str) and not field_value:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_summary."
                f"{field} must not be an empty string marker: {source}"
            )
    return summary


def _validate_orchestrator_operation_risk_rollup(
    value: Any,
    *,
    source: Path,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_rollup must be "
            f"an object: {source}"
        )
    rollup = deepcopy(value)
    expected_pairs = {
        "schema_version": ORCHESTRATOR_OPERATION_RISK_ROLLUP_SCHEMA_VERSION,
        "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        "decision_owner": "lab",
        "scheduler_owner": "orchestrator",
    }
    for key, expected in expected_pairs.items():
        if rollup.get(key) != expected:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_rollup."
                f"{key} must be {expected}: {source}"
            )
    if rollup.get("not_a_deployment_decision") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_rollup."
            f"not_a_deployment_decision must be true: {source}"
        )
    risk_level = rollup.get("risk_level")
    if risk_level is not None and not isinstance(risk_level, str):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_rollup."
            f"risk_level must be a string when present: {source}"
        )
    primary_reasons = rollup.get("primary_reasons")
    if primary_reasons is not None and (
        not isinstance(primary_reasons, list)
        or not all(isinstance(item, str) for item in primary_reasons)
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_risk_rollup."
            f"primary_reasons must be a string list when present: {source}"
        )
    affected_tasks = rollup.get("affected_tasks")
    if affected_tasks is not None:
        if not isinstance(affected_tasks, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_risk_rollup."
                f"affected_tasks must be an object when present: {source}"
            )
        for key, items in affected_tasks.items():
            if not isinstance(key, str):
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed operation_risk_rollup."
                    f"affected_tasks keys must be strings: {source}"
                )
            if not isinstance(items, list) or not all(
                isinstance(item, str) for item in items
            ):
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed operation_risk_rollup."
                    f"affected_tasks.{key} must be a string list: {source}"
                )
    return rollup


def _validate_orchestrator_candidate_operation_context(
    candidate_context: dict[str, Any],
    *,
    source: Path,
) -> None:
    operation = candidate_context.get("operation")
    if not isinstance(operation, dict):
        return
    _validate_orchestrator_stale_drop_summary(
        operation.get("stale_drop_summary"),
        source=source,
    )
    _validate_orchestrator_operation_risk_rollup(
        operation.get("operation_risk_rollup"),
        source=source,
    )
    _validate_orchestrator_operation_timeline_summary(
        operation.get("operation_timeline_summary"),
        source=source,
    )


def _validate_orchestrator_operation_timeline_summary(
    value: Any,
    *,
    source: Path,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_timeline_summary must be "
            f"an object: {source}"
        )
    summary = deepcopy(value)
    if (
        summary.get("schema_version")
        != ORCHESTRATOR_OPERATION_TIMELINE_SUMMARY_SCHEMA_VERSION
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed operation_timeline_summary."
            "schema_version must be "
            f"{ORCHESTRATOR_OPERATION_TIMELINE_SUMMARY_SCHEMA_VERSION}: {source}"
        )
    for field in ("sample_counts", "queue", "latency", "policy"):
        field_value = summary.get(field)
        if field_value is not None and not isinstance(field_value, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_timeline_summary."
                f"{field} must be an object when present: {source}"
            )
    for field in ("review_hints",):
        field_value = summary.get(field)
        if field_value is not None and (
            not isinstance(field_value, list)
            or not all(isinstance(item, str) for item in field_value)
        ):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_timeline_summary."
                f"{field} must be a string list when present: {source}"
            )
    affected_tasks = summary.get("affected_tasks")
    if affected_tasks is not None:
        if not isinstance(affected_tasks, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed operation_timeline_summary."
                f"affected_tasks must be an object when present: {source}"
            )
        for key, items in affected_tasks.items():
            if not isinstance(key, str):
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed operation_timeline_summary."
                    f"affected_tasks keys must be strings: {source}"
                )
            if not isinstance(items, list) or not all(
                isinstance(item, str) for item in items
            ):
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed operation_timeline_summary."
                    f"affected_tasks.{key} must be a string list: {source}"
                )
    _validate_orchestrator_stale_drop_summary(
        summary.get("stale_drop"),
        source=source,
    )
    return summary


def _validate_orchestrator_stale_drop_summary(
    value: Any,
    *,
    source: Path,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed stale_drop_summary must be "
            f"an object: {source}"
        )
    summary = deepcopy(value)
    expected_pairs = {
        "schema_version": ORCHESTRATOR_STALE_DROP_SUMMARY_SCHEMA_VERSION,
        "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
    }
    for key, expected in expected_pairs.items():
        if summary.get(key) != expected:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed stale_drop_summary."
                f"{key} must be {expected}: {source}"
            )
    if summary.get("not_a_deployment_decision") is not True:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed stale_drop_summary."
            f"not_a_deployment_decision must be true: {source}"
        )
    for field in ("stale_drop_count", "total_drop_count"):
        field_value = summary.get(field)
        if type(field_value) is not int or field_value < 0:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed stale_drop_summary."
                f"{field} must be a non-negative integer: {source}"
            )
    for field in ("stale_drop_reasons", "task_counts"):
        field_value = summary.get(field)
        if field_value is not None and not isinstance(field_value, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed stale_drop_summary."
                f"{field} must be an object when present: {source}"
            )
    tasks = summary.get("tasks_with_stale_drop")
    if tasks is not None and (
        not isinstance(tasks, list)
        or not all(isinstance(item, str) for item in tasks)
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed stale_drop_summary."
            f"tasks_with_stale_drop must be a string list when present: {source}"
        )
    return summary


def _validate_orchestrator_producer_context(
    value: Any,
    *,
    source: Path,
    require_device_local_producer: bool = False,
) -> None:
    if value is None:
        if require_device_local_producer:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer is "
                f"required for device-local producer validation: {source}"
            )
        return
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed candidate_context.producer must be "
            f"an object: {source}"
        )
    list_fields = (
        "producer_sources",
        "device_local_producer_sources",
    )
    for field in list_fields:
        field_value = value.get(field)
        if field_value is None and not require_device_local_producer:
            continue
        valid_string_list = isinstance(field_value, list) and all(
            isinstance(item, str) for item in field_value
        )
        if not valid_string_list:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"{field} must be a string list: {source}"
            )
        if require_device_local_producer and (
            not field_value or not all(field_value)
        ):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"{field} must be a non-empty string list for device-local "
                f"producer validation: {source}"
            )
    producer_sources = value.get("producer_sources")
    device_local_sources = value.get("device_local_producer_sources")
    if isinstance(producer_sources, list) and isinstance(device_local_sources, list):
        missing_from_sources = sorted(set(device_local_sources) - set(producer_sources))
        if missing_from_sources:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                "device_local_producer_sources must also appear in "
                f"producer_sources: {', '.join(missing_from_sources)}: {source}"
            )
    sources_by_task = value.get("producer_sources_by_task")
    if sources_by_task is None and not require_device_local_producer:
        sources_by_task = None
    else:
        if not isinstance(sources_by_task, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"producer_sources_by_task must be an object: {source}"
            )
        if require_device_local_producer and not sources_by_task:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                "producer_sources_by_task must be a non-empty object for "
                f"device-local producer validation: {source}"
            )
        task_sources: set[str] = set()
        for task_name, sources in sources_by_task.items():
            if not isinstance(task_name, str) or not task_name:
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed candidate_context.producer."
                    f"producer_sources_by_task keys must be non-empty strings: "
                    f"{source}"
                )
            if (
                not isinstance(sources, list)
                or not sources
                or not all(
                    isinstance(item, str) and item for item in sources
                )
            ):
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed candidate_context.producer."
                    f"producer_sources_by_task.{task_name} must be a "
                    f"non-empty string list: {source}"
                )
            task_sources.update(sources)
        if isinstance(device_local_sources, list):
            missing_from_task_sources = sorted(
                set(device_local_sources) - task_sources
            )
            if missing_from_task_sources:
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed candidate_context.producer."
                    "device_local_producer_sources must also appear in "
                    "producer_sources_by_task: "
                    f"{', '.join(missing_from_task_sources)}: {source}"
                )
    stage_by_task = value.get("producer_stage_by_task")
    if stage_by_task is None and not require_device_local_producer:
        stage_by_task = None
    else:
        if not isinstance(stage_by_task, dict):
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"producer_stage_by_task must be an object: {source}"
            )
        if require_device_local_producer and not stage_by_task:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                "producer_stage_by_task must be a non-empty object for "
                f"device-local producer validation: {source}"
            )
        for task_name, stage in stage_by_task.items():
            if not isinstance(task_name, str) or not task_name:
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed candidate_context.producer."
                    f"producer_stage_by_task keys must be non-empty strings: "
                    f"{source}"
                )
            if not isinstance(stage, str) or not stage:
                raise RuntimeTelemetryHistoryError(
                    "Orchestrator telemetry feed candidate_context.producer."
                    f"producer_stage_by_task.{task_name} must be a non-empty "
                    f"string: {source}"
                )
    if (
        ("operation_context_role" in value or require_device_local_producer)
        and value.get("operation_context_role")
        != ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE
    ):
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed candidate_context.producer."
            "operation_context_role must be supplemental: "
            f"{source}"
        )
    for field in (
        "producer_event_count",
        "device_local_event_count",
        "device_local_task_count",
    ):
        field_value = value.get(field)
        if field_value is None and not require_device_local_producer:
            continue
        if type(field_value) is not int:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"{field} must be an integer: {source}"
            )
        if require_device_local_producer and field_value <= 0:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed candidate_context.producer."
                f"{field} must be a positive integer for device-local "
                f"producer validation: {source}"
            )


def _validate_optional_mapping_value(
    mapping_hint: dict[str, Any],
    key: str,
    expected: str,
    source: Path,
) -> None:
    if key not in mapping_hint:
        return
    if mapping_hint.get(key) != expected:
        raise RuntimeTelemetryHistoryError(
            "Orchestrator telemetry feed "
            f"edgeenv_mapping_hint.{key} must be {expected}: {source}"
        )


def _validate_orchestrator_feed_scope(
    orchestrator_contexts: dict[str, dict[str, Any]],
    records: list[RegistryRecord],
) -> None:
    if not orchestrator_contexts:
        return
    selected_run_ids = {record.run_id for record in records}
    for run_id in sorted(orchestrator_contexts):
        if run_id not in selected_run_ids:
            raise RuntimeTelemetryHistoryError(
                "Orchestrator telemetry feed run is not selected in this history "
                f"export: {run_id}"
            )


def _sequence_sort_value(value: Any) -> tuple[int, float | str]:
    if isinstance(value, (int, float)):
        return (0, float(value))
    return (1, str(value or ""))


def _telemetry_fields(entries: list[dict[str, Any]]) -> list[str]:
    fields: set[str] = set()
    for entry in entries:
        telemetry = entry.get("runtime_telemetry")
        if not isinstance(telemetry, dict):
            continue
        fields.update(str(key) for key in telemetry.keys())
    return sorted(fields)


def _telemetry_coverage_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    coverage_entries: list[dict[str, Any]] = []
    expected_fields: set[str] = set()
    observed_fields: set[str] = set()
    missing_fields: set[str] = set()
    ratios: list[float] = []
    missing_telemetry_failure_values: set[bool] = set()
    run_summaries: list[dict[str, Any]] = []
    missing_field_runs: list[dict[str, Any]] = []

    for entry in entries:
        telemetry = entry.get("runtime_telemetry")
        if not isinstance(telemetry, dict):
            continue
        coverage = telemetry.get("coverage")
        if not isinstance(coverage, dict):
            continue
        run_id = entry.get("run_id")
        run_id_value = run_id if isinstance(run_id, str) else ""
        coverage_entries.append(coverage)
        expected = _string_items(coverage.get("expected_fields"))
        observed = _string_items(coverage.get("observed_fields"))
        missing = _string_items(coverage.get("missing_fields"))
        expected_fields.update(expected)
        observed_fields.update(observed)
        missing_fields.update(missing)
        ratio = coverage.get("coverage_ratio")
        ratio_value = float(ratio) if isinstance(ratio, (int, float)) else None
        if isinstance(ratio, (int, float)):
            ratios.append(float(ratio))
        missing_telemetry_is_failure = coverage.get("missing_telemetry_is_failure")
        if isinstance(missing_telemetry_is_failure, bool):
            missing_telemetry_failure_values.add(missing_telemetry_is_failure)
        run_summary = {
            "run_id": run_id_value,
            "coverage_present": True,
            "expected_fields": sorted(expected),
            "observed_fields": sorted(observed),
            "missing_fields": sorted(missing),
            "expected_field_count": coverage.get("expected_field_count"),
            "observed_field_count": coverage.get("observed_field_count"),
            "missing_field_count": coverage.get("missing_field_count"),
            "coverage_ratio": ratio_value,
            "missing_telemetry_is_failure": missing_telemetry_is_failure,
        }
        run_summaries.append(run_summary)
        if missing:
            missing_field_runs.append(
                {
                    "run_id": run_id_value,
                    "missing_fields": sorted(missing),
                    "missing_field_count": len(missing),
                    "missing_telemetry_is_failure": missing_telemetry_is_failure,
                }
            )

    return {
        "runs_with_coverage": len(coverage_entries),
        "runs_without_coverage": max(len(entries) - len(coverage_entries), 0),
        "expected_fields": sorted(expected_fields),
        "observed_fields": sorted(observed_fields),
        "missing_fields": sorted(missing_fields),
        "coverage_ratio_min": min(ratios) if ratios else None,
        "coverage_ratio_max": max(ratios) if ratios else None,
        "missing_telemetry_is_failure_values": sorted(
            missing_telemetry_failure_values
        ),
        "any_missing_telemetry_is_failure": any(missing_telemetry_failure_values),
        "missing_field_run_count": len(missing_field_runs),
        "missing_field_runs": missing_field_runs,
        "run_summaries": run_summaries,
    }


def _runtime_telemetry_history_seed(
    telemetry: dict[str, Any],
    *,
    run_id: str,
) -> dict[str, Any] | None:
    history_seed = telemetry.get("history_seed")
    if history_seed is None:
        return None
    _validate_runtime_history_seed(
        history_seed,
        label=f"runtime_telemetry.history_seed for run {run_id}",
    )
    return deepcopy(history_seed)


def _validate_runtime_history_seed(value: Any, *, label: str) -> None:
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed must be an object: {label}"
        )
    schema_version = value.get("schema_version")
    if schema_version != RUNTIME_TELEMETRY_HISTORY_SEED_SCHEMA_VERSION:
        raise RuntimeTelemetryHistoryError(
            "Unsupported Runtime telemetry history seed schema: "
            f"{schema_version or '<missing>'}: {label}"
        )
    if value.get("registry_owner") != "edgeenv":
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed registry_owner must be edgeenv: {label}"
        )
    if value.get("decision_owner") != "lab":
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed decision_owner must be lab: {label}"
        )
    if value.get("production_monitoring") is not False:
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed production_monitoring must be false: {label}"
        )
    if value.get("missing_telemetry_is_failure") is not False:
        raise RuntimeTelemetryHistoryError(
            "Runtime telemetry history seed missing_telemetry_is_failure must be "
            f"false: {label}"
        )
    points = value.get("points")
    if not isinstance(points, list) or not points:
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed points must be a non-empty list: {label}"
        )
    source_result = value.get("source_result")
    if source_result is not None and not isinstance(source_result, dict):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed source_result must be an object: {label}"
        )
    run_config = value.get("run_config")
    if run_config is not None:
        _validate_runtime_history_seed_run_config(
            run_config,
            label=f"{label}.run_config",
        )


def _validate_runtime_history_seed_run_config(value: Any, *, label: str) -> None:
    if not isinstance(value, dict):
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry history seed run_config must be an object: {label}"
        )
    for field in ("batch", "height", "width", "warmup", "runs"):
        field_value = value.get(field)
        if type(field_value) is not int:
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history seed run_config."
                f"{field} must be an integer: {label}"
            )
    timeout_ms = value.get("timeout_ms")
    if timeout_ms is not None and type(timeout_ms) is not int:
        raise RuntimeTelemetryHistoryError(
            "Runtime telemetry history seed run_config.timeout_ms must be "
            f"an integer or null: {label}"
        )
    for field in ("input_mode", "input_preprocess", "power_mode", "jetson_clocks"):
        field_value = value.get(field)
        if not isinstance(field_value, str):
            raise RuntimeTelemetryHistoryError(
                "Runtime telemetry history seed run_config."
                f"{field} must be a string: {label}"
            )


def _history_seed_run_count(entries: list[dict[str, Any]]) -> int:
    return sum(
        1
        for entry in entries
        if isinstance(entry.get("runtime_telemetry_history_seed"), dict)
    )


def _history_seed_run_config_count(entries: list[dict[str, Any]]) -> int:
    return sum(1 for entry in entries if _has_runtime_history_seed_run_config(entry))


def _has_runtime_history_seed_run_config(entry: dict[str, Any]) -> bool:
    history_seed = entry.get("runtime_telemetry_history_seed")
    if not isinstance(history_seed, dict):
        return False
    return isinstance(history_seed.get("run_config"), dict)


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _is_monotonic(values: list[int | float]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))
