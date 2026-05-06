from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edgeenv.result.schema import RunResult


REQUIRED_FIELDS = [
    "model_hash",
    "input_shape",
    "input_dtype",
    "task",
    "precision",
    "batch_size",
    "warmup_runs",
    "repeat_runs",
    "include_preprocess",
    "include_postprocess",
]


@dataclass(frozen=True)
class ComparabilityReport:
    comparable: str
    mode: str | None
    reasons: list[str]


def check_comparability(a: RunResult, b: RunResult) -> ComparabilityReport:
    differences: list[str] = []
    for field in REQUIRED_FIELDS:
        left = _comparison_value(a, field)
        right = _comparison_value(b, field)
        if left != right:
            differences.append(_difference_reason(field))

    if differences:
        return ComparabilityReport(comparable="No", mode=None, reasons=differences)

    conditional_reasons: list[str] = [
        "Same model hash",
        "Same input shape",
        "Same precision",
        "Same benchmark protocol",
    ]
    runtime_diff = a.runtime != b.runtime
    target_diff = a.target != b.target
    if runtime_diff or target_diff:
        if runtime_diff:
            conditional_reasons.append("Different runtime or execution provider")
        if target_diff:
            conditional_reasons.append("Different target")
        mode = "runtime-comparison" if runtime_diff else "target-comparison"
        return ComparabilityReport(
            comparable="Conditional",
            mode=mode,
            reasons=conditional_reasons,
        )

    return ComparabilityReport(
        comparable="Yes",
        mode="same-condition",
        reasons=conditional_reasons,
    )


def _comparison_value(result: RunResult, field: str) -> Any:
    if field == "model_hash":
        return result.model.model_hash
    return getattr(result.protocol, field)


def _difference_reason(field: str) -> str:
    labels = {
        "model_hash": "Different model hash",
        "input_shape": "Different input shape",
        "input_dtype": "Different input dtype",
        "task": "Different task",
        "precision": "Different precision",
        "batch_size": "Different batch size",
        "warmup_runs": "Different warmup runs",
        "repeat_runs": "Different repeat runs",
        "include_preprocess": "Different preprocess inclusion",
        "include_postprocess": "Different postprocess inclusion",
    }
    return labels[field]
