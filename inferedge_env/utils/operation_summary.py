from __future__ import annotations

import json
from typing import Any, Iterable


OPERATION_SUMMARY_FIELDS = (
    "mode",
    "max_queue",
    "queue_pressure",
    "deadline_missed",
    "fallback",
    "dropped",
)


def compact_operation_summary_label(value: dict[str, Any] | None) -> str:
    """Return a compact reviewer-facing operation context label."""
    if not isinstance(value, dict):
        return "absent"
    summary = compact_operation_summary(value)
    return "operation_summary: " + ", ".join(
        f"{field}={_label_value(summary[field])}"
        for field in OPERATION_SUMMARY_FIELDS
    )


def compact_operation_summary(value: dict[str, Any]) -> dict[str, Any]:
    contexts = tuple(_operation_contexts(value))
    return {
        "mode": _first_value(
            contexts,
            (
                "mode",
                "operation_mode",
                "scenario_mode",
                "execution_mode",
                "runtime_mode",
                "operation_path",
                "path",
                "health_reason",
            ),
        ),
        "max_queue": _first_value(
            contexts,
            (
                "max_total_queue_depth",
                "max_queue_depth",
                "max_queue",
                "queue_depth",
            ),
        ),
        "queue_pressure": _first_value(
            contexts,
            (
                "queue_pressure_reason",
                "queue_pressure",
                "queue_backlog_reason",
            ),
        )
        or _first_nested_value(
            contexts,
            "queue_pressure_context",
            ("reason", "label"),
        ),
        "deadline_missed": _first_value(
            contexts,
            (
                "deadline_missed_count",
                "deadline_missed",
                "deadline_miss_count",
                "deadline_missed_total",
            ),
        ),
        "fallback": _first_value(
            contexts,
            (
                "fallback_count",
                "fallback",
                "fallback_total",
            ),
        ),
        "dropped": _first_value(
            contexts,
            (
                "dropped_count",
                "drop_count",
                "dropped_task_count",
                "dropped_frame_count",
                "stale_drop_count",
            ),
        ),
    }


def operation_summary_rows_from_runtime_context(
    context: dict[str, Any] | None,
) -> list[tuple[str, str]]:
    if not isinstance(context, dict):
        return []
    rows: list[tuple[str, str]] = []
    for label in ("baseline", "candidate"):
        run_context = context.get(label)
        if not isinstance(run_context, dict):
            continue
        operation_context = run_context.get("orchestrator_operation_context")
        if not isinstance(operation_context, dict):
            continue
        rows.append((label, compact_operation_summary_label(operation_context)))
    return rows


def _operation_contexts(value: dict[str, Any]) -> Iterable[dict[str, Any]]:
    operation_context = value.get("orchestrator_operation_context")
    if isinstance(operation_context, dict):
        yield from _operation_contexts(operation_context)

    risk_summary = value.get("operation_risk_summary")
    if isinstance(risk_summary, dict):
        yield risk_summary

    candidate_context = value.get("candidate_context")
    if isinstance(candidate_context, dict):
        candidate_operation = candidate_context.get("operation")
        if isinstance(candidate_operation, dict):
            yield candidate_operation
        yield candidate_context

    operation = value.get("operation")
    if isinstance(operation, dict):
        yield operation

    yield value


def _first_value(
    contexts: Iterable[dict[str, Any]],
    keys: tuple[str, ...],
) -> Any:
    for context in contexts:
        for key in keys:
            if key not in context:
                continue
            value = context[key]
            if value is not None and value != "":
                return value
    return None


def _first_nested_value(
    contexts: Iterable[dict[str, Any]],
    container_key: str,
    keys: tuple[str, ...],
) -> Any:
    for context in contexts:
        container = context.get(container_key)
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = container.get(key)
            if value is not None and value != "":
                return value
    return None


def _label_value(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
