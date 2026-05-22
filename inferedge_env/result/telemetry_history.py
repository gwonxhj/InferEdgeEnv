from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inferedge_env.registry.db import RunRegistry
from inferedge_env.registry.models import RegistryRecord
from inferedge_env.result.schema import RunResult
from inferedge_env.result.writer import load_result


RUNTIME_TELEMETRY_HISTORY_SCHEMA_VERSION = "edgeenv.runtime-telemetry-history.v1"


class RuntimeTelemetryHistoryError(ValueError):
    """Raised when runtime telemetry history cannot be built safely."""


def build_runtime_telemetry_history(
    edgeenv_root: Path | str,
    *,
    run_ids: list[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    root = Path(edgeenv_root)
    registry = RunRegistry(root / "runs.db")
    records = _select_records(registry, run_ids)
    generated = generated_at or datetime.now(timezone.utc)

    entries: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for record in records:
        result = _load_record_result(record)
        if result.runtime_telemetry is None:
            missing.append(
                {
                    "run_id": result.run_id,
                    "reason": "runtime_telemetry_missing",
                }
            )
            continue
        entries.append(_history_entry(result))

    entries.sort(
        key=lambda entry: (
            str(entry.get("telemetry_timestamp") or ""),
            _sequence_sort_value(entry.get("execution_sequence_id")),
            entry["created_at"],
            entry["run_id"],
        )
    )
    missing.sort(key=lambda item: item["run_id"])
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
            "missing_telemetry_runs": len(missing),
        },
        "runs": entries,
        "missing_telemetry": missing,
        "notes": [
            "Runtime telemetry history is local replay evidence, not production monitoring.",
            "Missing telemetry is recorded as an evidence gap, not a failed benchmark run.",
            "Comparability-first regression analysis must still run before delta judgement.",
        ],
    }


def write_runtime_telemetry_history(
    edgeenv_root: Path | str,
    output_path: Path | str,
    *,
    run_ids: list[str] | None = None,
) -> dict[str, Any]:
    payload = build_runtime_telemetry_history(edgeenv_root, run_ids=run_ids)
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


def inspect_runtime_telemetry_history(payload: dict[str, Any]) -> dict[str, Any]:
    validate_runtime_telemetry_history(payload)
    runs = payload.get("runs", [])
    missing = payload.get("missing_telemetry", [])
    run_ids = [entry["run_id"] for entry in runs]
    timestamps = [
        entry.get("telemetry_timestamp")
        for entry in runs
        if entry.get("telemetry_timestamp") is not None
    ]
    sequence_ids = [entry.get("execution_sequence_id") for entry in runs]
    numeric_sequence_ids = [
        value for value in sequence_ids if isinstance(value, (int, float))
    ]
    return {
        "schema_version": payload["schema_version"],
        "valid": True,
        "summary": payload["summary"],
        "source": payload.get("source", {}),
        "replay": {
            "run_ids": run_ids,
            "telemetry_fields": _telemetry_fields(runs),
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


def _history_entry(result: RunResult) -> dict[str, Any]:
    telemetry = result.runtime_telemetry
    if telemetry is None:
        raise RuntimeTelemetryHistoryError(
            f"Runtime telemetry missing for run: {result.run_id}"
        )
    return {
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


def _is_monotonic(values: list[int | float]) -> bool:
    return all(left <= right for left, right in zip(values, values[1:]))
