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
