from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from inferedge_env import __version__
from inferedge_env.compare.comparability import check_comparability
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.schema import RunResult
from inferedge_env.result.writer import load_result
from inferedge_env.utils.operation_summary import compact_operation_summary_label


REQUIRED_RUN_FILES = [
    "result.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
]


class BundleSummaryError(ValueError):
    """Raised when a bundle handoff summary cannot be generated."""


@dataclass(frozen=True)
class BundleScenario:
    label: str
    run_id_a: str
    run_id_b: str


@dataclass(frozen=True)
class BundleSummaryOptions:
    source_device: str | None = None
    edgeenv_version: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RunEvidence:
    run_id: str
    result: RunResult
    run_dir: Path
    exported_files_label: str
    sampler_evidence_label: str
    resource_source: str
    runtime_operation_source: str
    runtime_operation_summary_label: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ScenarioSummary:
    scenario: BundleScenario
    run_a: _RunEvidence
    run_b: _RunEvidence
    comparable: str
    mode: str
    metrics_delta: str


def parse_bundle_scenario(value: str) -> BundleScenario:
    parts = value.split(":")
    if len(parts) != 3 or not all(parts):
        raise BundleSummaryError(
            "Scenario must use the form <label>:<run_id_a>:<run_id_b>"
        )
    label, run_id_a, run_id_b = parts
    return BundleScenario(label=label, run_id_a=run_id_a, run_id_b=run_id_b)


def render_bundle_summary_markdown(
    scenarios: list[BundleScenario],
    edgeenv_root: Path | str = ".edgeenv",
    options: BundleSummaryOptions | None = None,
) -> str:
    if not scenarios:
        raise BundleSummaryError("At least one --scenario is required")
    _reject_duplicate_scenario_labels(scenarios)

    opts = options or BundleSummaryOptions()
    registry = RunRegistry(Path(edgeenv_root) / "runs.db")
    summaries = [_summarize_scenario(registry, scenario) for scenario in scenarios]
    warnings = _collect_warnings(summaries)
    notes = tuple(opts.notes) or (
        "Sampler/resource/runtime operation evidence was supplemental and did "
        "not appear as a compare judgement reason.",
        "No model, dataset, engine, cloud DB, auth, dashboard, leaderboard, "
        "or target remote execution semantics are included.",
    )

    lines = [
        "# EdgeEnv Evidence Bundle Handoff",
        "",
        "## Scope",
        "",
        f"- Source device: {opts.source_device or 'unspecified'}",
        f"- EdgeEnv version: {opts.edgeenv_version or __version__}",
        "- Bundle type: successful-run",
        "- Export/import validation: previously completed before summary generation",
        "- Import registry policy: runs.db excluded, registry rebuilt from result.json",
        "",
        "## Bundles",
        "",
        "| Scenario | Run A | Run B | Exported files | Sampler evidence | Resource source | Runtime operation source | Operation summary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table(summary.scenario.label),
                    _escape_table(summary.scenario.run_id_a),
                    _escape_table(summary.scenario.run_id_b),
                    _escape_table(_combine_labels(
                        summary.run_a.exported_files_label,
                        summary.run_b.exported_files_label,
                    )),
                    _escape_table(_combine_labels(
                        summary.run_a.sampler_evidence_label,
                        summary.run_b.sampler_evidence_label,
                    )),
                    _escape_table(_combine_labels(
                        summary.run_a.resource_source,
                        summary.run_b.resource_source,
                    )),
                    _escape_table(_combine_labels(
                        summary.run_a.runtime_operation_source,
                        summary.run_b.runtime_operation_source,
                    )),
                    _escape_table(_combine_labels(
                        summary.run_a.runtime_operation_summary_label,
                        summary.run_b.runtime_operation_summary_label,
                    )),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Imported Compare Results",
            "",
            "| Scenario | Comparable | Mode | Metrics Delta | Expected |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for summary in summaries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table(summary.scenario.label),
                    summary.comparable,
                    summary.mode,
                    summary.metrics_delta,
                    "yes",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Evidence Integrity",
            "",
            "- Manifest schema: edgeenv.export.v1",
            "- Required files present: result/config/target/env/stdout/stderr",
            "- Sampler metadata present: " + _presence_summary(
                evidence.sampler_evidence_label != "absent"
                for summary in summaries
                for evidence in (summary.run_a, summary.run_b)
            ),
            "- Raw sampler artifacts present: " + _raw_artifact_summary(summaries),
            "- SHA-256/byte-size verification: previously validated during import",
            "- Unsafe paths/runs.db excluded: previously validated during import",
            "",
            "## Notes",
            "",
        ]
    )
    lines.extend(f"- {note}" for note in notes)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def _summarize_scenario(
    registry: RunRegistry,
    scenario: BundleScenario,
) -> _ScenarioSummary:
    run_a = _load_run_evidence(registry, scenario.run_id_a)
    run_b = _load_run_evidence(registry, scenario.run_id_b)
    report = check_comparability(run_a.result, run_b.result)
    mode = report.mode or "none"
    metrics_delta = (
        "present"
        if report.comparable == "Yes" and report.mode == "same-condition"
        else "absent"
    )
    return _ScenarioSummary(
        scenario=scenario,
        run_a=run_a,
        run_b=run_b,
        comparable=report.comparable,
        mode=mode,
        metrics_delta=metrics_delta,
    )


def _load_run_evidence(registry: RunRegistry, run_id: str) -> _RunEvidence:
    try:
        record = registry.show(run_id)
    except KeyError as exc:
        raise BundleSummaryError(str(exc)) from exc

    result_path = Path(record.result_path)
    run_dir = result_path.parent
    missing = [name for name in REQUIRED_RUN_FILES if not (run_dir / name).is_file()]
    if missing:
        raise BundleSummaryError(
            f"Required run artifact file missing for {run_id}: {missing[0]}"
        )
    try:
        result = load_result(result_path)
    except (OSError, ValueError) as exc:
        raise BundleSummaryError(f"Invalid result artifact for {run_id}") from exc

    sampler_label, warnings = _sampler_evidence_label(run_id, run_dir)
    resource_source = (
        result.resource_metrics.source
        if result.resource_metrics is not None and result.resource_metrics.source
        else "absent"
    )
    runtime_operation_source = _runtime_operation_source(result)
    runtime_operation_summary_label = compact_operation_summary_label(
        result.runtime_operation_summary
    )
    exported_files_label = "core + sampler" if sampler_label != "absent" else "core"
    return _RunEvidence(
        run_id=run_id,
        result=result,
        run_dir=run_dir,
        exported_files_label=exported_files_label,
        sampler_evidence_label=sampler_label,
        resource_source=resource_source,
        runtime_operation_source=runtime_operation_source,
        runtime_operation_summary_label=runtime_operation_summary_label,
        warnings=tuple(warnings),
    )


def _runtime_operation_source(result: RunResult) -> str:
    if result.runtime_operation_summary is None:
        return "absent"
    source = result.runtime_operation_summary.get("source")
    if isinstance(source, str) and source:
        return source
    return "present"


def _sampler_evidence_label(run_id: str, run_dir: Path) -> tuple[str, list[str]]:
    metadata_path = run_dir / "sampler" / "metadata.json"
    if not metadata_path.exists():
        return "absent", [f"{run_id}: sampler metadata absent"]
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleSummaryError(f"Invalid sampler metadata for {run_id}") from exc
    if not isinstance(metadata, dict):
        raise BundleSummaryError(f"Sampler metadata must be a JSON object for {run_id}")
    raw_artifacts = metadata.get("raw_artifacts", [])
    if not isinstance(raw_artifacts, list):
        raise BundleSummaryError(f"Sampler raw_artifacts must be a list for {run_id}")
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, str):
            raise BundleSummaryError(
                f"Sampler raw_artifacts entries must be strings for {run_id}"
            )
        raw_path = PurePosixPath(raw_artifact)
        if raw_path.is_absolute() or ".." in raw_path.parts:
            raise BundleSummaryError(
                f"Unsafe sampler raw artifact path for {run_id}: {raw_artifact}"
            )
        if not (run_dir / Path(*raw_path.parts)).is_file():
            raise BundleSummaryError(
                f"Sampler raw artifact missing for {run_id}: {raw_artifact}"
            )
    if raw_artifacts:
        return "metadata + raw log", []
    return "metadata only", [f"{run_id}: sampler raw artifacts absent"]


def _reject_duplicate_scenario_labels(scenarios: list[BundleScenario]) -> None:
    seen: set[str] = set()
    for scenario in scenarios:
        if scenario.label in seen:
            raise BundleSummaryError(f"Duplicate scenario label: {scenario.label}")
        seen.add(scenario.label)


def _collect_warnings(summaries: list[_ScenarioSummary]) -> list[str]:
    warnings: list[str] = []
    for summary in summaries:
        warnings.extend(summary.run_a.warnings)
        warnings.extend(summary.run_b.warnings)
        if summary.run_a.resource_source == "absent":
            warnings.append(f"{summary.scenario.run_id_a}: resource metrics absent")
        if summary.run_b.resource_source == "absent":
            warnings.append(f"{summary.scenario.run_id_b}: resource metrics absent")
    return sorted(set(warnings))


def _combine_labels(left: str, right: str) -> str:
    if left == right:
        return left
    return f"{left} / {right}"


def _presence_summary(values: Iterable[bool]) -> str:
    items = list(values)
    if all(items):
        return "yes"
    if any(items):
        return "partial"
    return "no"


def _raw_artifact_summary(summaries: list[_ScenarioSummary]) -> str:
    labels = [
        evidence.sampler_evidence_label
        for summary in summaries
        for evidence in (summary.run_a, summary.run_b)
    ]
    if all(label == "metadata + raw log" for label in labels):
        return "yes"
    if any(label == "metadata + raw log" for label in labels):
        return "partial"
    return "no"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")
