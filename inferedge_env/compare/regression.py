from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inferedge_env.compare.comparability import ComparabilityReport, check_comparability
from inferedge_env.result.schema import RunResult


MEAN_REVIEW_PCT = 15.0
P99_HIGH_PCT = 25.0
FPS_REVIEW_PCT = -20.0
MEMORY_WARNING_PCT = 30.0


@dataclass(frozen=True)
class RegressionReport:
    baseline_run_id: str
    candidate_run_id: str
    regression_detected: bool
    regression_type: str
    severity: str
    comparable: bool
    mode: str
    evidence: dict[str, Any]
    recommendation: str
    comparability: ComparabilityReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_run_id": self.baseline_run_id,
            "candidate_run_id": self.candidate_run_id,
            "regression_detected": self.regression_detected,
            "regression_type": self.regression_type,
            "severity": self.severity,
            "comparable": self.comparable,
            "mode": self.mode,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "comparability": {
                "comparable": self.comparability.comparable,
                "mode": self.comparability.mode,
                "reasons": self.comparability.reasons,
            },
        }


def analyze_regression(
    baseline: RunResult,
    candidate: RunResult,
) -> RegressionReport:
    comparability = check_comparability(baseline, candidate)
    if comparability.comparable != "Yes" or comparability.mode != "same-condition":
        mode = _blocked_mode(comparability)
        return RegressionReport(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            regression_detected=False,
            regression_type="not_evaluated",
            severity="medium" if mode in {"protocol_mismatch", "not_comparable"} else "low",
            comparable=False,
            mode=mode,
            evidence={
                "reason": "regression_requires_same_condition_comparability",
                "comparability_reasons": comparability.reasons,
            },
            recommendation=_blocked_recommendation(mode),
            comparability=comparability,
        )

    evidence = _same_condition_evidence(baseline, candidate)
    triggered = _triggered_thresholds(evidence)
    regression_type = _regression_type(triggered)
    severity = _severity(triggered)
    recommendation = "review_required" if triggered else "no_action_required"
    if triggered and all(item["type"] == "resource" for item in triggered):
        recommendation = "resource_warning"

    return RegressionReport(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        regression_detected=bool(triggered),
        regression_type=regression_type,
        severity=severity,
        comparable=True,
        mode="same-condition",
        evidence={
            **evidence,
            "triggered_thresholds": triggered,
        },
        recommendation=recommendation,
        comparability=comparability,
    )


def render_regression_markdown(report: RegressionReport) -> str:
    payload = report.to_dict()
    lines = [
        "# EdgeEnv Runtime Regression Report",
        "",
        "## Summary",
        "",
        f"- Baseline run: `{report.baseline_run_id}`",
        f"- Candidate run: `{report.candidate_run_id}`",
        f"- Comparable: `{str(report.comparable).lower()}`",
        f"- Mode: `{report.mode}`",
        f"- Regression detected: `{str(report.regression_detected).lower()}`",
        f"- Regression type: `{report.regression_type}`",
        f"- Severity: `{report.severity}`",
        f"- Recommendation: `{report.recommendation}`",
        "",
        "## Comparability",
        "",
        f"- Judgement: `{report.comparability.comparable}`",
        f"- Comparability mode: `{report.comparability.mode or ''}`",
        "",
        "Reasons:",
    ]
    lines.extend(f"- {reason}" for reason in report.comparability.reasons)
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            "```json",
            _json_dumps(payload["evidence"]),
            "```",
            "",
            "## Boundary",
            "",
            "This report is local-first regression evidence. It is not a cloud "
            "monitoring alert, public leaderboard, or production observability "
            "platform.",
            "",
        ]
    )
    return "\n".join(lines)


def _same_condition_evidence(
    baseline: RunResult,
    candidate: RunResult,
) -> dict[str, Any]:
    return {
        "mean_delta_pct": _percent_delta(
            baseline.metrics.latency_mean_ms,
            candidate.metrics.latency_mean_ms,
        ),
        "p95_delta_pct": _percent_delta(
            baseline.metrics.latency_p95_ms,
            candidate.metrics.latency_p95_ms,
        ),
        "p99_delta_pct": _percent_delta(
            baseline.metrics.latency_p99_ms,
            candidate.metrics.latency_p99_ms,
        ),
        "fps_delta_pct": _percent_delta(
            baseline.metrics.throughput_fps,
            candidate.metrics.throughput_fps,
        ),
        "memory_peak_delta_pct": _resource_percent_delta(
            baseline,
            candidate,
            "memory_peak_mb",
        ),
        "baseline": _metrics_payload(baseline),
        "candidate": _metrics_payload(candidate),
    }


def _metrics_payload(result: RunResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "latency_mean_ms": result.metrics.latency_mean_ms,
        "latency_p95_ms": result.metrics.latency_p95_ms,
        "latency_p99_ms": result.metrics.latency_p99_ms,
        "throughput_fps": result.metrics.throughput_fps,
    }
    if result.resource_metrics is not None:
        payload["memory_peak_mb"] = result.resource_metrics.memory_peak_mb
    return payload


def _resource_percent_delta(
    baseline: RunResult,
    candidate: RunResult,
    field: str,
) -> float | None:
    if baseline.resource_metrics is None or candidate.resource_metrics is None:
        return None
    baseline_value = getattr(baseline.resource_metrics, field)
    candidate_value = getattr(candidate.resource_metrics, field)
    if baseline_value is None or candidate_value is None:
        return None
    return _percent_delta(baseline_value, candidate_value)


def _percent_delta(baseline: float, candidate: float) -> float | None:
    if baseline == 0:
        return None
    return round(((candidate - baseline) / baseline) * 100, 6)


def _triggered_thresholds(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    _append_if_triggered(
        triggered,
        name="mean_latency_review",
        metric="mean_delta_pct",
        regression_type="latency",
        severity="medium",
        observed=evidence["mean_delta_pct"],
        threshold=MEAN_REVIEW_PCT,
        comparison=">=",
    )
    _append_if_triggered(
        triggered,
        name="p99_latency_high",
        metric="p99_delta_pct",
        regression_type="latency",
        severity="high",
        observed=evidence["p99_delta_pct"],
        threshold=P99_HIGH_PCT,
        comparison=">=",
    )
    _append_if_triggered(
        triggered,
        name="fps_drop_review",
        metric="fps_delta_pct",
        regression_type="latency",
        severity="medium",
        observed=evidence["fps_delta_pct"],
        threshold=FPS_REVIEW_PCT,
        comparison="<=",
    )
    _append_if_triggered(
        triggered,
        name="memory_peak_warning",
        metric="memory_peak_delta_pct",
        regression_type="resource",
        severity="warning",
        observed=evidence["memory_peak_delta_pct"],
        threshold=MEMORY_WARNING_PCT,
        comparison=">=",
    )
    return triggered


def _append_if_triggered(
    triggered: list[dict[str, Any]],
    *,
    name: str,
    metric: str,
    regression_type: str,
    severity: str,
    observed: float | None,
    threshold: float,
    comparison: str,
) -> None:
    if observed is None:
        return
    if comparison == ">=":
        is_triggered = observed >= threshold
    elif comparison == "<=":
        is_triggered = observed <= threshold
    else:
        raise ValueError(f"Unsupported threshold comparison: {comparison}")
    if not is_triggered:
        return
    triggered.append(
        {
            "name": name,
            "type": regression_type,
            "metric": metric,
            "observed": observed,
            "threshold": threshold,
            "comparison": comparison,
            "severity": severity,
        }
    )


def _regression_type(triggered: list[dict[str, Any]]) -> str:
    if not triggered:
        return "none"
    types = {item["type"] for item in triggered}
    if len(types) == 1:
        return next(iter(types))
    return "mixed"


def _severity(triggered: list[dict[str, Any]]) -> str:
    severities = {item["severity"] for item in triggered}
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    if "warning" in severities:
        return "warning"
    return "low"


def _blocked_mode(report: ComparabilityReport) -> str:
    if report.mode is not None:
        return report.mode
    if any(reason.startswith("Different model hash") for reason in report.reasons):
        return "not_comparable"
    return "protocol_mismatch"


def _blocked_recommendation(mode: str) -> str:
    if mode == "runtime-comparison":
        return "review_as_runtime_comparison"
    if mode == "target-comparison":
        return "review_as_target_comparison"
    if mode == "protocol_mismatch":
        return "rerun_with_matching_protocol"
    return "do_not_compare"


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, indent=2, sort_keys=True)
