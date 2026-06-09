from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from inferedge_env import __version__
from inferedge_env.compare.comparability import check_comparability
from inferedge_env.compare.regression import (
    analyze_regression,
    render_regression_markdown,
)
from inferedge_env.config.bench_config import load_benchmark_config
from inferedge_env.config.target_profile import TargetProfile, load_target_profile
from inferedge_env.registry.db import RunRegistry
from inferedge_env.registry.models import RegistryRecord, ResourceMetricRecord
from inferedge_env.report.bundle_summary import (
    BundleSummaryError,
    BundleSummaryOptions,
    parse_bundle_scenario,
    render_bundle_summary_markdown,
)
from inferedge_env.result.exporter import (
    RunExportError,
    RunImportError,
    export_failed_run,
    export_successful_run,
    import_failed_run,
    import_successful_run,
    validate_successful_run_import,
)
from inferedge_env.result.lab_handoff import (
    RuntimeIntelligenceLabHandoffError,
    write_runtime_intelligence_lab_handoff_manifest,
)
from inferedge_env.result.schema import (
    FAILED_RUN_SCHEMA_VERSION,
    ResourceMetrics,
    RunResult,
)
from inferedge_env.result.telemetry_history import (
    RuntimeTelemetryHistoryError,
    inspect_runtime_telemetry_history,
    load_runtime_telemetry_history,
    write_runtime_telemetry_history,
)
from inferedge_env.result.writer import (
    FailedRunArtifactWriter,
    ResultArtifactWriter,
    SamplerArtifactError,
    build_run_result,
    load_result,
    new_run_id,
    write_sampler_artifacts,
)
from inferedge_env.runners.fake import FakeRunner
from inferedge_env.runners.local import LocalRunner, LocalRunnerError
from inferedge_env.utils.operation_summary import (
    compact_operation_summary_label,
    operation_summary_rows_from_runtime_context,
)


app = typer.Typer(help="EdgeEnv benchmark runner and local result registry.")
profile_app = typer.Typer(help="Target profile commands.")
bench_app = typer.Typer(help="Benchmark config and run commands.")
runs_app = typer.Typer(help="Local run registry commands.")
runs_sampler_app = typer.Typer(help="Sampler metadata inspection commands.")
runs_resources_app = typer.Typer(help="Resource metric index commands.")
runs_telemetry_app = typer.Typer(help="Runtime telemetry evidence commands.")
failed_runs_app = typer.Typer(help="Failed local run artifact commands.")
report_app = typer.Typer(help="Report and comparison commands.")
console = Console()
_RESOURCE_LOOKUP_NOTE = (
    "Resource metrics are supplemental lookup evidence; they do not affect "
    "comparability or ranking."
)

app.add_typer(profile_app, name="profile")
app.add_typer(bench_app, name="bench")
app.add_typer(runs_app, name="runs")
runs_app.add_typer(runs_sampler_app, name="sampler")
runs_app.add_typer(runs_resources_app, name="resources")
runs_app.add_typer(runs_telemetry_app, name="telemetry")
app.add_typer(failed_runs_app, name="failed-runs")
app.add_typer(report_app, name="report")


@app.command()
def doctor() -> None:
    """Check that the EdgeEnv CLI is available."""
    console.print("[bold green]EdgeEnv doctor: OK[/bold green]")
    console.print(f"Version: {__version__}")
    console.print("Runner support: fake, local")
    console.print("Registry: .edgeenv/runs.db")


@profile_app.command("validate")
def validate_profile(profile_path: Path) -> None:
    """Validate a target profile YAML file."""
    try:
        profile = load_target_profile(profile_path)
    except ValueError as exc:
        _fail(
            str(exc),
            hint=(
                "Check that the target profile is valid YAML and includes "
                "target_name, target_type, board_name, os, and runtime_tags. "
                "v1 target_type values are fake and local."
            ),
        )
    console.print(f"[green]Valid target profile:[/green] {profile.target_name}")


@bench_app.command("validate")
def validate_bench(bench_config_path: Path) -> None:
    """Validate a benchmark config YAML file."""
    try:
        config = load_benchmark_config(bench_config_path)
    except ValueError as exc:
        _fail(
            str(exc),
            hint=(
                "Check required benchmark YAML fields and protocol values. "
                "For local commands, also confirm command, timeout_seconds, "
                "working_directory, and uppercase extra_env keys."
            ),
        )
    console.print(f"[green]Valid benchmark config:[/green] {config.name}")


@bench_app.command("run")
def run_benchmark(
    target_path: Path = typer.Option(..., "--target", help="Target profile YAML path."),
    config_path: Path = typer.Option(..., "--config", help="Benchmark config YAML path."),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Run a benchmark and persist result artifacts plus registry metadata."""
    try:
        target = load_target_profile(target_path)
        config = load_benchmark_config(config_path)
    except ValueError as exc:
        _fail(
            str(exc),
            hint=(
                "Validate both files first with `edgeenv profile validate` and "
                "`edgeenv bench validate`."
            ),
        )

    runner = _runner_for_target(target)
    run_id = new_run_id()
    try:
        if isinstance(runner, LocalRunner):
            runner_result = runner.run(
                config,
                target,
                run_id=run_id,
                artifact_dir=edgeenv_root / "runs" / run_id,
            )
        else:
            runner_result = runner.run(config, target)
    except LocalRunnerError as exc:
        shutil.rmtree(edgeenv_root / "runs" / run_id, ignore_errors=True)
        failed_dir = FailedRunArtifactWriter(edgeenv_root).write(
            config=config,
            target=target,
            config_path=config_path,
            target_path=target_path,
            error_message=str(exc),
            stdout=exc.stdout,
            stderr=exc.stderr,
            return_code=exc.return_code,
            run_id=run_id,
        )
        console.print(
            f"[yellow]Failed run artifact:[/yellow] {failed_dir}",
            soft_wrap=True,
        )
        console.print("[yellow]Registry:[/yellow] not updated")
        _fail(
            str(exc),
            hint=_local_runner_error_hint(str(exc), run_id, edgeenv_root),
        )
    result = build_run_result(config, target, runner_result, run_id=run_id)
    sampler_metadata_path: Path | None = None
    try:
        run_dir = ResultArtifactWriter(edgeenv_root).write(
            result=result,
            config_path=config_path,
            target_path=target_path,
            stdout=runner_result.stdout,
            stderr=runner_result.stderr,
        )
        if runner_result.sampler_summary is not None:
            sampler_metadata_path = write_sampler_artifacts(
                run_dir,
                runner_result.sampler_summary,
            )
    except (OSError, SamplerArtifactError) as exc:
        _fail(str(exc))
    result_path = run_dir / "result.json"
    RunRegistry(edgeenv_root / "runs.db").insert(result, result_path)

    console.print("[bold green]Benchmark run stored[/bold green]")
    console.print(f"Run ID: {result.run_id}")
    console.print(f"Result: {result_path}", soft_wrap=True)
    console.print(f"Latency mean: {result.metrics.latency_mean_ms} ms")
    console.print(_resource_metrics_status(result.resource_metrics), soft_wrap=True)
    console.print(
        _runtime_operation_summary_status(result.runtime_operation_summary),
        soft_wrap=True,
    )
    console.print(_runtime_telemetry_status(result.runtime_telemetry), soft_wrap=True)
    if sampler_metadata_path is not None:
        console.print(
            f"Sampler metadata: stored ({sampler_metadata_path})",
            soft_wrap=True,
        )


@runs_app.command("list")
def list_runs(
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """List locally registered runs."""
    records = RunRegistry(edgeenv_root / "runs.db").list_runs()
    table = Table(title="EdgeEnv Runs")
    table.add_column("Run ID")
    table.add_column("Created")
    table.add_column("Target")
    table.add_column("Model")
    table.add_column("Runtime")
    table.add_column("Mean ms", justify="right")
    for record in records:
        table.add_row(
            record.run_id,
            record.created_at.isoformat(),
            record.target["target_name"],
            record.model["model_name"],
            record.runtime["runtime"],
            str(record.metrics["latency_mean_ms"]),
        )
    console.print(table)


@runs_app.command("show")
def show_run(
    run_id: str,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Show a run registry record."""
    try:
        record = RunRegistry(edgeenv_root / "runs.db").show(run_id)
    except KeyError as exc:
        _fail(str(exc))
    console.print(
        json.dumps(_show_payload(record), indent=2, sort_keys=True),
        soft_wrap=True,
    )


@runs_sampler_app.command("show")
def show_run_sampler(
    run_id: str,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Show sampler metadata for a successful run."""
    try:
        record = RunRegistry(edgeenv_root / "runs.db").show(run_id)
        payload = _sampler_show_payload(record)
    except (KeyError, OSError, ValueError) as exc:
        _fail(str(exc))
    console.print(json.dumps(payload, indent=2, sort_keys=True), soft_wrap=True)


@runs_resources_app.command("list")
def list_run_resources(
    metric: str | None = typer.Option(
        None,
        "--metric",
        help="Optional resource metric name to filter by.",
    ),
    source: str | None = typer.Option(
        None,
        "--source",
        help="Optional resource metric source to filter by.",
    ),
    min_value: float | None = typer.Option(
        None,
        "--min-value",
        help="Optional inclusive lower bound for metric values.",
    ),
    max_value: float | None = typer.Option(
        None,
        "--max-value",
        help="Optional inclusive upper bound for metric values.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable lookup results as JSON.",
    ),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """List indexed resource metrics for registered successful runs."""
    try:
        records = RunRegistry(edgeenv_root / "runs.db").list_resource_metrics(
            metric_name=metric,
            source=source,
            min_value=min_value,
            max_value=max_value,
        )
    except ValueError as exc:
        _fail(str(exc))
    if json_output:
        console.print(
            json.dumps(
                _resource_metric_lookup_payload(
                    records,
                    metric=metric,
                    source=source,
                    min_value=min_value,
                    max_value=max_value,
                ),
                indent=2,
                sort_keys=True,
            ),
            soft_wrap=True,
        )
        return
    console.print("[bold]EdgeEnv Resource Metrics[/bold]")
    console.print(_RESOURCE_LOOKUP_NOTE, soft_wrap=True)
    console.print(f"Results: {len(records)}")
    if not records:
        console.print("No indexed resource metrics found.")
        return
    console.print(f"Sources: {_format_resource_sources(records)}", soft_wrap=True)
    for record in records:
        console.print(f"- Run ID: {record.run_id}", soft_wrap=True)
        console.print(
            "  Metric: "
            f"{record.metric_name}={_format_float(record.metric_value)} "
            f"{record.unit}",
            soft_wrap=True,
        )
        console.print(f"  Source: {record.source or ''}", soft_wrap=True)


@runs_telemetry_app.command("export-history")
def export_runtime_telemetry_history(
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write the runtime telemetry history JSON artifact.",
    ),
    run_ids: Optional[list[str]] = typer.Option(
        None,
        "--run-id",
        help="Optional run id to include. Repeat to build a selected replay set.",
    ),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
    orchestrator_feeds: Optional[list[Path]] = typer.Option(
        None,
        "--orchestrator-feed",
        help=(
            "Optional InferEdgeOrchestrator EdgeEnv telemetry feed JSON to attach "
            "as supplemental operation context. Repeat for multiple run IDs."
        ),
    ),
) -> None:
    """Export local runtime telemetry evidence as a replayable history artifact."""
    try:
        payload = write_runtime_telemetry_history(
            edgeenv_root,
            output_path,
            run_ids=run_ids,
            orchestrator_feeds=orchestrator_feeds,
        )
    except (RuntimeTelemetryHistoryError, OSError) as exc:
        _fail(str(exc), hint=_telemetry_history_error_hint(str(exc)))
    summary = payload["summary"]
    console.print("[bold green]Runtime telemetry history exported[/bold green]")
    console.print(f"Output: {output_path}", soft_wrap=True)
    console.print(f"Runs scanned: {summary['registered_runs']}")
    console.print(f"Telemetry entries: {summary['telemetry_runs']}")
    console.print(f"History seed entries: {summary.get('history_seed_runs', 0)}")
    console.print(
        "History seed run_config entries: "
        f"{summary.get('history_seed_run_config_runs', 0)}"
    )
    console.print(f"Missing telemetry: {summary['missing_telemetry_runs']}")
    console.print(
        f"Orchestrator context entries: {summary.get('orchestrator_feed_runs', 0)}"
    )
    console.print(
        "Scope: local replay evidence; not production monitoring.",
        soft_wrap=True,
    )


@runs_telemetry_app.command("inspect-history")
def inspect_runtime_telemetry_history_command(
    history_path: Path,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable replay summary as JSON.",
    ),
    require_device_local_producer: bool = typer.Option(
        False,
        "--require-device-local-producer",
        help=(
            "Fail unless preserved Orchestrator context includes device-local "
            "candidate_context.producer lineage."
        ),
    ),
) -> None:
    """Validate and summarize a runtime telemetry history replay artifact."""
    try:
        payload = load_runtime_telemetry_history(history_path)
        summary = inspect_runtime_telemetry_history(
            payload,
            require_device_local_producer=require_device_local_producer,
        )
    except RuntimeTelemetryHistoryError as exc:
        _fail(str(exc), hint=_telemetry_history_input_error_hint(str(exc)))
    if json_output:
        console.print(json.dumps(summary, indent=2, sort_keys=True), soft_wrap=True)
        return
    replay = summary["replay"]
    console.print("[bold green]Runtime telemetry history valid[/bold green]")
    console.print(f"Input: {history_path}", soft_wrap=True)
    console.print(f"Schema: {summary['schema_version']}")
    console.print(f"Replay runs: {len(replay['run_ids'])}")
    console.print(f"Telemetry fields: {', '.join(replay['telemetry_fields']) or '-'}")
    coverage = replay.get("telemetry_coverage", {})
    if isinstance(coverage, dict):
        console.print(
            "Telemetry coverage runs: "
            f"{coverage.get('runs_with_coverage', 0)}"
        )
        console.print(
            "Telemetry coverage missing fields: "
            f"{', '.join(coverage.get('missing_fields', [])) or '-'}",
            soft_wrap=True,
        )
        console.print(
            "Telemetry coverage missing field runs: "
            f"{coverage.get('missing_field_run_count', 0)}"
        )
    console.print(
        "Runtime history seed runs: "
        f"{len(replay.get('history_seed_run_ids', []))}"
    )
    console.print(
        "Runtime history seed run_config runs: "
        f"{len(replay.get('history_seed_run_config_run_ids', []))}"
    )
    console.print(
        "Orchestrator context runs: "
        f"{len(replay.get('orchestrator_context_run_ids', []))}"
    )
    console.print(
        "Missing telemetry Orchestrator context runs: "
        f"{len(replay.get('missing_orchestrator_context_run_ids', []))}"
    )
    console.print(
        "Device-local producer context runs: "
        f"{len(replay.get('device_local_producer_context_run_ids', []))}"
    )
    console.print(
        "Producer-lineage guard alignment runs: "
        f"{len(replay.get('producer_lineage_guard_alignment_run_ids', []))}"
    )
    console.print(f"Evidence gaps: {replay['evidence_gap_count']}")
    console.print(f"Missing run IDs: {', '.join(replay['missing_run_ids']) or '-'}")
    console.print(
        "Scope: read-only local replay validation; not production monitoring.",
        soft_wrap=True,
    )


@runs_app.command("export")
def export_run(
    run_id: str,
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write the exported run evidence zip.",
    ),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Export a successful run evidence bundle as a zip archive."""
    try:
        record = RunRegistry(edgeenv_root / "runs.db").show(run_id)
        archive_path = export_successful_run(
            Path(record.result_path).parent,
            output_path,
        )
    except (KeyError, RunExportError, OSError) as exc:
        _fail(str(exc), hint=_export_error_hint(str(exc)))
    console.print("[bold green]Run evidence exported[/bold green]")
    console.print(f"Run ID: {run_id}")
    console.print(f"Archive: {archive_path}", soft_wrap=True)


@runs_app.command("import")
def import_run(
    archive_path: Path,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Import a successful run evidence zip and rebuild the registry row."""
    registry = RunRegistry(edgeenv_root / "runs.db")
    try:
        plan = validate_successful_run_import(archive_path)
        try:
            registry.show(plan.result.run_id)
        except KeyError:
            pass
        else:
            _fail(
                f"Run already exists in registry: {plan.result.run_id}",
                hint=_import_error_hint("Run already exists in registry"),
            )
        result, run_dir = import_successful_run(archive_path, edgeenv_root)
        registry.insert(result, run_dir / "result.json")
    except (RunImportError, OSError) as exc:
        _fail(str(exc), hint=_import_error_hint(str(exc)))
    console.print("[bold green]Run evidence imported[/bold green]")
    console.print(f"Run ID: {result.run_id}")
    console.print(f"Result: {run_dir / 'result.json'}", soft_wrap=True)


@failed_runs_app.command("list")
def list_failed_runs(
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """List failed local run artifacts."""
    failures = _load_failed_run_summaries(edgeenv_root)
    console.print("[bold]EdgeEnv Failed Runs[/bold]")
    if not failures:
        console.print("No failed run artifacts found.")
        return
    for failure in failures:
        console.print(f"- Run ID: {failure.get('run_id', '')}", soft_wrap=True)
        console.print(f"  Created: {failure.get('created_at', '')}", soft_wrap=True)
        console.print(
            f"  Benchmark: {failure.get('benchmark_name', '')}",
            soft_wrap=True,
        )
        console.print(f"  Target: {failure.get('target_name', '')}", soft_wrap=True)
        console.print(
            f"  Return Code: {_optional_value(failure.get('return_code'))}",
            soft_wrap=True,
        )
        console.print(f"  Error: {failure.get('error_message', '')}", soft_wrap=True)


@failed_runs_app.command("show")
def show_failed_run(
    run_id: str,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
    log_chars: int = typer.Option(
        2000,
        "--log-chars",
        min=0,
        help="Maximum stdout/stderr characters to include in the JSON output.",
    ),
) -> None:
    """Show a failed local run artifact bundle."""
    try:
        failed_dir = _failed_run_dir(edgeenv_root, run_id)
        failure = _read_failure_json(failed_dir)
    except (OSError, ValueError) as exc:
        _fail(str(exc))

    payload = {
        "artifact_path": str(failed_dir),
        "failure": failure,
        "files": {
            "failure": str(failed_dir / "failure.json"),
            "config": str(failed_dir / "config.yaml"),
            "target": str(failed_dir / "target.yaml"),
            "env": str(failed_dir / "env.json"),
            "stdout": str(failed_dir / "stdout.log"),
            "stderr": str(failed_dir / "stderr.log"),
        },
        "stdout": _read_log_preview(failed_dir / "stdout.log", log_chars),
        "stderr": _read_log_preview(failed_dir / "stderr.log", log_chars),
    }
    console.print(json.dumps(payload, indent=2, sort_keys=True), soft_wrap=True)


@failed_runs_app.command("export")
def export_failed_run_artifact(
    run_id: str,
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write the exported failed-run evidence zip.",
    ),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Export a failed-run diagnostic evidence bundle as a zip archive."""
    try:
        failed_dir = _failed_run_dir(edgeenv_root, run_id)
        archive_path = export_failed_run(failed_dir, output_path)
    except (RunExportError, OSError, ValueError) as exc:
        _fail(str(exc), hint=_export_error_hint(str(exc)))
    console.print("[bold green]Failed-run evidence exported[/bold green]")
    console.print(f"Run ID: {run_id}")
    console.print(f"Archive: {archive_path}", soft_wrap=True)


@failed_runs_app.command("import")
def import_failed_run_artifact(
    archive_path: Path,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Import a failed-run diagnostic evidence zip."""
    try:
        failure, failed_dir = import_failed_run(archive_path, edgeenv_root)
    except (RunImportError, OSError) as exc:
        _fail(str(exc), hint=_import_error_hint(str(exc)))
    console.print("[bold green]Failed-run evidence imported[/bold green]")
    console.print(f"Run ID: {failure['run_id']}")
    console.print(f"Artifact: {failed_dir}", soft_wrap=True)


@report_app.command("compare")
def compare_runs(
    run_id_a: str,
    run_id_b: str,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
) -> None:
    """Compare whether two runs are directly comparable."""
    registry = RunRegistry(edgeenv_root / "runs.db")
    try:
        record_a = registry.show(run_id_a)
        record_b = registry.show(run_id_b)
    except KeyError as exc:
        _fail(str(exc))

    result_a = load_result(record_a.result_path)
    result_b = load_result(record_b.result_path)
    report = check_comparability(result_a, result_b)
    console.print(f"Comparable: {report.comparable}")
    if report.mode:
        console.print(f"Mode: {report.mode}")
    console.print("Reason:")
    for reason in report.reasons:
        console.print(f"- {reason}")
    if report.comparable == "Yes" and report.mode == "same-condition":
        _print_same_condition_metric_delta(result_a, result_b)


@report_app.command("regression")
def regression_report(
    baseline_run_id: str,
    candidate_run_id: str,
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
    output_json: Path | None = typer.Option(
        None,
        "--output-json",
        help="Optional path to write the machine-readable regression report.",
    ),
    output_markdown: Path | None = typer.Option(
        None,
        "--output-md",
        help="Optional path to write the Markdown regression report.",
    ),
    telemetry_history: Path | None = typer.Option(
        None,
        "--telemetry-history",
        help=(
            "Optional runtime telemetry history JSON artifact to attach as "
            "supplemental regression context."
        ),
    ),
) -> None:
    """Generate comparability-first runtime regression evidence."""
    registry = RunRegistry(edgeenv_root / "runs.db")
    try:
        baseline_record = registry.show(baseline_run_id)
        candidate_record = registry.show(candidate_run_id)
    except KeyError as exc:
        _fail(str(exc))

    baseline = load_result(baseline_record.result_path)
    candidate = load_result(candidate_record.result_path)
    telemetry_history_payload = _load_telemetry_history_payload(telemetry_history)
    report = analyze_regression(
        baseline,
        candidate,
        telemetry_history=telemetry_history_payload,
    )
    payload = report.to_dict()

    if output_json is not None:
        try:
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            _fail(str(exc))
    if output_markdown is not None:
        try:
            output_markdown.parent.mkdir(parents=True, exist_ok=True)
            output_markdown.write_text(
                render_regression_markdown(report),
                encoding="utf-8",
            )
        except OSError as exc:
            _fail(str(exc))

    console.print("[bold]EdgeEnv Runtime Regression Report[/bold]")
    console.print(f"Baseline: {report.baseline_run_id}")
    console.print(f"Candidate: {report.candidate_run_id}")
    console.print(f"Comparable: {str(report.comparable).lower()}")
    console.print(f"Mode: {report.mode}")
    console.print(f"Regression detected: {str(report.regression_detected).lower()}")
    console.print(f"Regression type: {report.regression_type}")
    console.print(f"Severity: {report.severity}")
    console.print(f"Recommendation: {report.recommendation}")
    console.print("Comparability:")
    console.print(f"- Judgement: {report.comparability.comparable}")
    if report.comparability.mode:
        console.print(f"- Mode: {report.comparability.mode}")
    for reason in report.comparability.reasons:
        console.print(f"- {reason}")
    if report.runtime_telemetry_context is not None:
        _print_runtime_telemetry_context(report.runtime_telemetry_context)
    if report.comparable and report.mode == "same-condition":
        console.print("Regression Evidence:")
        _print_regression_evidence(report.evidence)
    else:
        console.print("Regression Evidence: not evaluated")
    if output_json is not None:
        console.print(f"JSON report: {output_json}", soft_wrap=True)
    if output_markdown is not None:
        console.print(f"Markdown report: {output_markdown}", soft_wrap=True)


@report_app.command("runtime-intelligence-handoff")
def runtime_intelligence_handoff_manifest(
    baseline_result: Path = typer.Option(
        ...,
        "--baseline-result",
        help="Baseline Runtime/EdgeEnv result JSON path.",
    ),
    candidate_result: Path = typer.Option(
        ...,
        "--candidate-result",
        help="Candidate Runtime/EdgeEnv result JSON path.",
    ),
    edgeenv_regression_report: Path = typer.Option(
        ...,
        "--edgeenv-regression-report",
        help="EdgeEnv runtime regression report JSON path.",
    ),
    output_path: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write the EdgeEnv-to-Lab handoff manifest JSON.",
    ),
    telemetry_history: Path
    | None = typer.Option(
        None,
        "--telemetry-history",
        help="Optional runtime telemetry history JSON path used by the report.",
    ),
) -> None:
    """Write EdgeEnv producer-side Runtime Intelligence handoff metadata."""
    try:
        payload = write_runtime_intelligence_lab_handoff_manifest(
            output_path=output_path,
            baseline_result_path=baseline_result,
            candidate_result_path=candidate_result,
            edgeenv_regression_report_path=edgeenv_regression_report,
            telemetry_history_path=telemetry_history,
        )
    except (RuntimeIntelligenceLabHandoffError, OSError) as exc:
        _fail(str(exc), hint=_runtime_intelligence_handoff_error_hint(str(exc)))

    summary = payload["edgeenv_report_summary"]
    console.print(
        "[bold green]Runtime Intelligence handoff manifest written[/bold green]"
    )
    console.print(f"Output: {output_path}", soft_wrap=True)
    console.print(f"Baseline: {summary.get('baseline_run_id')}")
    console.print(f"Candidate: {summary.get('candidate_run_id')}")
    console.print(f"Mode: {summary.get('mode')}")
    console.print(
        "Orchestrator context: "
        f"{str(summary.get('orchestrator_context_present')).lower()}"
    )
    if summary.get("history_seed_runs") is not None:
        console.print(f"History seed entries: {summary.get('history_seed_runs')}")
    marker_runs = [
        str(item.get("run_id"))
        for item in summary.get("history_seed_run_config_markers", [])
        if isinstance(item, dict) and item.get("run_id")
    ]
    if marker_runs:
        console.print(
            "History seed run_config markers: "
            f"{', '.join(marker_runs)}"
        )
    device_local_run_ids = summary.get("device_local_producer_context_run_ids")
    if device_local_run_ids:
        console.print(
            "Device-local producer contexts: "
            f"{', '.join(device_local_run_ids)}"
        )
    guard_alignment_run_ids = summary.get("producer_lineage_guard_alignment_run_ids")
    if guard_alignment_run_ids:
        console.print(
            "Producer-lineage guard alignment: "
            f"{', '.join(guard_alignment_run_ids)}"
        )
    external_evidence_types = payload.get("lab_bundle_alignment", {}).get(
        "external_aiguard_required_evidence_types",
        [],
    )
    if external_evidence_types:
        console.print(
            "External AIGuard evidence types: "
            f"{', '.join(external_evidence_types)}",
            soft_wrap=True,
        )
    console.print("Lab remains the final deployment decision owner.", soft_wrap=True)


@report_app.command("bundle-summary")
def bundle_summary(
    scenarios: list[str] = typer.Option(
        ...,
        "--scenario",
        help="Scenario in the form <label>:<run_id_a>:<run_id_b>.",
    ),
    edgeenv_root: Path = typer.Option(
        Path(".edgeenv"),
        "--edgeenv-root",
        help="Directory for EdgeEnv artifacts and registry.",
    ),
    output_path: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional path to write the Markdown report.",
    ),
    source_device: str | None = typer.Option(
        None,
        "--source-device",
        help="Optional source device name for the Markdown scope section.",
    ),
    note: list[str] | None = typer.Option(
        None,
        "--note",
        help="Optional note line to include in the Markdown report.",
    ),
) -> None:
    """Generate a read-only Markdown handoff summary for imported run pairs."""
    try:
        parsed = [parse_bundle_scenario(value) for value in scenarios]
        markdown = render_bundle_summary_markdown(
            parsed,
            edgeenv_root=edgeenv_root,
            options=BundleSummaryOptions(
                source_device=source_device,
                notes=tuple(note or ()),
            ),
        )
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
            console.print("[bold green]Bundle summary written[/bold green]")
            console.print(f"Report: {output_path}", soft_wrap=True)
            return
    except (BundleSummaryError, OSError) as exc:
        _fail(str(exc))
    console.print(markdown, markup=False, soft_wrap=True)


def _runner_for_target(target: TargetProfile) -> FakeRunner | LocalRunner:
    if target.target_type == "fake":
        return FakeRunner()
    if target.target_type == "local":
        return LocalRunner()
    _fail(f"Unsupported target_type for v1: {target.target_type}")


def _show_payload(record: RegistryRecord) -> dict:
    payload = record.model_dump(mode="json")
    try:
        result = load_result(payload["result_path"])
    except (OSError, ValueError):
        return payload
    if result.resource_metrics is not None:
        payload["resource_metrics"] = result.resource_metrics.model_dump(
            mode="json",
            exclude_none=True,
        )
    if result.runtime_operation_summary is not None:
        payload["runtime_operation_summary"] = result.runtime_operation_summary
        payload["runtime_operation_summary_label"] = compact_operation_summary_label(
            result.runtime_operation_summary
        )
    if result.runtime_telemetry is not None:
        payload["runtime_telemetry"] = result.runtime_telemetry
    return payload


def _load_telemetry_history_payload(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        return load_runtime_telemetry_history(path)
    except RuntimeTelemetryHistoryError as exc:
        _fail(str(exc), hint=_telemetry_history_input_error_hint(str(exc)))


def _runtime_intelligence_handoff_error_hint(message: str) -> str:
    if "schema_version" in message or "orchestrator_operation_context" in message:
        return (
            "Regenerate the telemetry history and regression report from the same "
            "EdgeEnv evidence chain before creating the Lab handoff manifest."
        )
    if "run_id" in message:
        return (
            "Use the baseline/candidate result JSON files that produced the "
            "EdgeEnv regression report."
        )
    return (
        "Check the result JSON paths, EdgeEnv regression report path, and optional "
        "telemetry history path."
    )


def _sampler_show_payload(record: RegistryRecord) -> dict[str, Any]:
    run_dir = Path(record.result_path).parent
    metadata_path = run_dir / "sampler" / "metadata.json"
    if not metadata_path.is_file():
        raise ValueError(f"Sampler metadata not found for run: {record.run_id}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid sampler metadata JSON: {metadata_path}") from exc
    if not isinstance(metadata, dict):
        raise ValueError(f"Sampler metadata must be a JSON object: {metadata_path}")
    raw_artifacts = metadata.get("raw_artifacts", [])
    if not isinstance(raw_artifacts, list):
        raise ValueError(
            f"Sampler metadata raw_artifacts must be a list: {metadata_path}"
        )
    files = {
        "metadata": str(metadata_path),
        "raw_artifacts": {
            str(path): str(run_dir / str(path))
            for path in raw_artifacts
            if isinstance(path, str)
        },
    }
    return {
        "run_id": record.run_id,
        "artifact_path": str(run_dir),
        "sampler_metadata_path": str(metadata_path),
        "sampler_name": metadata.get("sampler_name"),
        "sample_count": metadata.get("sample_count"),
        "warnings": metadata.get("warnings", []),
        "raw_artifacts": raw_artifacts,
        "files": files,
        "metadata": metadata,
    }


def _load_failed_run_summaries(edgeenv_root: Path) -> list[dict[str, Any]]:
    failed_root = edgeenv_root / "failed-runs"
    if not failed_root.exists():
        return []
    failures: list[dict[str, Any]] = []
    for failed_dir in sorted(path for path in failed_root.iterdir() if path.is_dir()):
        try:
            failures.append(_read_failure_json(failed_dir))
        except (OSError, ValueError):
            continue
    return sorted(
        failures,
        key=lambda failure: str(failure.get("created_at", "")),
        reverse=True,
    )


def _failed_run_dir(edgeenv_root: Path, run_id: str) -> Path:
    if (
        not run_id
        or run_id in {".", ".."}
        or Path(run_id).parts != (run_id,)
        or "\\" in run_id
    ):
        raise ValueError(f"Invalid failed run id: {run_id}")
    failed_dir = edgeenv_root / "failed-runs" / run_id
    if not failed_dir.is_dir():
        raise ValueError(f"Failed run not found: {run_id}")
    return failed_dir


def _read_failure_json(failed_dir: Path) -> dict[str, Any]:
    failure_path = failed_dir / "failure.json"
    try:
        payload = json.loads(failure_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid failed run artifact: {failure_path}") from exc
    if payload.get("schema_version") != FAILED_RUN_SCHEMA_VERSION:
        raise ValueError(f"Unsupported failed run schema: {failure_path}")
    return payload


def _read_log_preview(path: Path, max_chars: int) -> str:
    if max_chars == 0:
        return ""
    text = path.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[truncated]"


def _optional_value(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _resource_metrics_status(resource_metrics: ResourceMetrics | None) -> str:
    if resource_metrics is None:
        return "Resource metrics: omitted"
    payload = resource_metrics.model_dump(mode="json", exclude_none=True)
    source = payload.get("source")
    measured_fields = sorted(key for key in payload if key != "source")
    if source and measured_fields:
        return (
            "Resource metrics: stored "
            f"(source={source}, fields={', '.join(measured_fields)})"
        )
    if source:
        return f"Resource metrics: stored (source={source})"
    if measured_fields:
        return f"Resource metrics: stored (fields={', '.join(measured_fields)})"
    return "Resource metrics: stored"


def _runtime_operation_summary_status(
    runtime_operation_summary: dict[str, Any] | None,
) -> str:
    if runtime_operation_summary is None:
        return "Runtime operation summary: omitted"
    source = runtime_operation_summary.get("source")
    if source:
        return f"Runtime operation summary: stored (source={source})"
    return "Runtime operation summary: stored"


def _runtime_telemetry_status(runtime_telemetry: dict[str, Any] | None) -> str:
    if runtime_telemetry is None:
        return "Runtime telemetry: omitted"
    schema = runtime_telemetry.get("schema_version")
    resource = runtime_telemetry.get("resource")
    source = resource.get("telemetry_source") if isinstance(resource, dict) else None
    if isinstance(schema, str) and schema and isinstance(source, str) and source:
        return f"Runtime telemetry: stored (schema={schema}, source={source})"
    if isinstance(schema, str) and schema:
        return f"Runtime telemetry: stored (schema={schema})"
    return "Runtime telemetry: stored"


def _resource_metric_lookup_payload(
    records: list[ResourceMetricRecord],
    *,
    metric: str | None,
    source: str | None,
    min_value: float | None,
    max_value: float | None,
) -> dict[str, Any]:
    return {
        "count": len(records),
        "filters": {
            "metric": metric,
            "source": source,
            "min_value": min_value,
            "max_value": max_value,
        },
        "note": _RESOURCE_LOOKUP_NOTE,
        "results": [
            {
                "run_id": record.run_id,
                "created_at": record.created_at.isoformat(),
                "target_name": record.target_name,
                "model_name": record.model_name,
                "metric_name": record.metric_name,
                "metric_value": record.metric_value,
                "unit": record.unit,
                "source": record.source,
            }
            for record in records
        ],
        "sources": _resource_source_counts(records),
    }


def _resource_source_counts(
    records: list[ResourceMetricRecord],
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for record in records:
        source = record.source or "unspecified"
        counts[source] = counts.get(source, 0) + 1
    return [
        {"source": source, "count": count}
        for source, count in sorted(counts.items())
    ]


def _format_resource_sources(records: list[ResourceMetricRecord]) -> str:
    counts = _resource_source_counts(records)
    if not counts:
        return "none"
    return ", ".join(
        f"{item['source']} ({item['count']})" for item in counts
    )


def _print_same_condition_metric_delta(a: RunResult, b: RunResult) -> None:
    console.print("Metrics Delta:")
    metric_specs = [
        ("latency_mean_ms", "ms"),
        ("latency_p50_ms", "ms"),
        ("latency_p95_ms", "ms"),
        ("latency_p99_ms", "ms"),
        ("throughput_fps", "fps"),
    ]
    for field, unit in metric_specs:
        left = getattr(a.metrics, field)
        right = getattr(b.metrics, field)
        console.print(_metric_delta_line(field, left, right, unit))


def _print_regression_evidence(evidence: dict[str, Any]) -> None:
    for field in [
        "mean_delta_pct",
        "p95_delta_pct",
        "p99_delta_pct",
        "fps_delta_pct",
        "memory_peak_delta_pct",
    ]:
        value = evidence.get(field)
        if value is None:
            console.print(f"- {field}: n/a")
        else:
            console.print(f"- {field}: {_format_signed_float(float(value))}%")
    triggered = evidence.get("triggered_thresholds", [])
    if not triggered:
        console.print("- triggered_thresholds: none")
        return
    console.print("- triggered_thresholds:")
    for item in triggered:
        console.print(
            "  - "
            f"{item['name']} ({item['metric']} {item['comparison']} "
            f"{item['threshold']}, observed {_format_float(float(item['observed']))}, "
            f"severity={item['severity']})",
            soft_wrap=True,
        )


def _print_runtime_telemetry_context(context: dict[str, Any]) -> None:
    console.print("Runtime Telemetry Context:")
    baseline = context.get("baseline", {})
    candidate = context.get("candidate", {})
    if isinstance(baseline, dict):
        console.print(
            "- baseline: "
            f"present={str(bool(baseline.get('result_telemetry_present'))).lower()}, "
            f"history={str(bool(baseline.get('history_entry_present'))).lower()}",
            soft_wrap=True,
        )
        _print_runtime_telemetry_coverage("baseline", baseline)
    if isinstance(candidate, dict):
        console.print(
            "- candidate: "
            f"present={str(bool(candidate.get('result_telemetry_present'))).lower()}, "
            f"history={str(bool(candidate.get('history_entry_present'))).lower()}",
            soft_wrap=True,
        )
        _print_runtime_telemetry_coverage("candidate", candidate)
    for label, summary in operation_summary_rows_from_runtime_context(context):
        console.print(f"- {label} {summary}", soft_wrap=True)
    gaps = context.get("evidence_gaps", [])
    if gaps:
        console.print("- evidence_gaps:")
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            console.print(
                f"  - {gap.get('run_id')}: {gap.get('reason')}",
                soft_wrap=True,
            )
    else:
        console.print("- evidence_gaps: none")
    console.print("- role: supplemental context, not a comparability gate")


def _print_runtime_telemetry_coverage(
    label: str,
    context: dict[str, Any],
) -> None:
    coverage = context.get("telemetry_coverage")
    if not isinstance(coverage, dict):
        coverage = context.get("history_telemetry_coverage")
    if not isinstance(coverage, dict):
        return
    missing_fields = coverage.get("missing_fields")
    if not isinstance(missing_fields, list):
        missing_fields = []
    console.print(
        f"- {label} coverage: "
        f"observed={coverage.get('observed_field_count', '-')}/"
        f"{coverage.get('expected_field_count', '-')}, "
        f"missing={', '.join(str(item) for item in missing_fields) or '-'}, "
        f"missing_is_failure="
        f"{str(bool(coverage.get('missing_telemetry_is_failure'))).lower()}",
        soft_wrap=True,
    )


def _metric_delta_line(field: str, left: float, right: float, unit: str) -> str:
    delta = right - left
    percent = _format_percent_delta(left, delta)
    return (
        f"- {field}: {_format_float(left)} {unit} -> {_format_float(right)} {unit} "
        f"(delta {_format_signed_float(delta)} {unit}, {percent})"
    )


def _format_percent_delta(baseline: float, delta: float) -> str:
    if baseline == 0:
        return "percent n/a"
    return f"{(delta / baseline) * 100:+.2f}%"


def _format_signed_float(value: float) -> str:
    if value > 0:
        return f"+{_format_float(value)}"
    return _format_float(value)


def _format_float(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." not in text:
        return f"{text}.0"
    return text


def _local_runner_error_hint(message: str, run_id: str, edgeenv_root: Path) -> str:
    inspect_command = (
        f"edgeenv failed-runs show {run_id} --edgeenv-root {edgeenv_root}"
    )
    if "Missing EDGEENV_METRICS_JSON" in message:
        return (
            "Emit one stdout line that starts with EDGEENV_METRICS_JSON= and "
            "contains latency_mean_ms, latency_p50_ms, latency_p95_ms, "
            f"latency_p99_ms, and throughput_fps. Inspect logs with: {inspect_command}"
        )
    if "Invalid EDGEENV_METRICS_JSON JSON" in message:
        return (
            "Write the primary metrics line with a structured JSON writer such "
            f"as json.dumps(...). Inspect stdout with: {inspect_command}"
        )
    if "Invalid local metrics schema" in message:
        return (
            "Primary metrics must include the five numeric latency/throughput "
            f"fields. Inspect captured stdout with: {inspect_command}"
        )
    if "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON" in message:
        return (
            "Resource metrics are optional. Omit EDGEENV_RESOURCE_METRICS_JSON= "
            "when the sampler cannot produce valid JSON, or write it with "
            f"json.dumps(...). Inspect stdout with: {inspect_command}"
        )
    if "Invalid local resource metrics schema" in message:
        return (
            "Resource metrics are supplemental. Use only supported numeric "
            f"ResourceMetrics fields, or omit the line. Inspect stdout with: {inspect_command}"
        )
    if "failed with exit code" in message:
        return (
            "The benchmark command exited before EdgeEnv could store a successful "
            f"run. Inspect stdout/stderr with: {inspect_command}"
        )
    if "timed out" in message:
        return (
            "The command exceeded timeout_seconds. Reduce the benchmark loop or "
            f"increase timeout_seconds, then inspect partial logs with: {inspect_command}"
        )
    if "Failed to start local benchmark command" in message:
        return (
            "Check the command path, quoting, working_directory, virtualenv, and "
            f"permissions. Inspect the failed-run artifact with: {inspect_command}"
        )
    return (
        "Inspect captured stdout/stderr and copied config/profile evidence with: "
        f"{inspect_command}"
    )


def _import_error_hint(message: str) -> str:
    if "already exists" in message or "already exists in registry" in message:
        return (
            "Import never overwrites existing evidence. Use a fresh --edgeenv-root "
            "or choose a bundle whose run_id has not been imported yet."
        )
    if "Checksum mismatch" in message or "Byte size mismatch" in message:
        return (
            "The bundle bytes do not match manifest.json. Re-export the run from "
            "the source workspace before importing again."
        )
    if "Unsafe archive entry path" in message or "Unsafe export archive path" in message:
        return (
            "The bundle contains an unsafe path. Do not edit zip contents manually; "
            "create bundles with `edgeenv runs export` or `edgeenv failed-runs export`."
        )
    if "Unsupported run evidence export schema" in message:
        return (
            "This EdgeEnv version cannot import that bundle schema. Use a compatible "
            "release or add an explicit migration before importing."
        )
    if "Unsupported run evidence bundle type" in message:
        return (
            "Use `edgeenv runs import` for successful-run bundles and "
            "`edgeenv failed-runs import` for failed-run diagnostic bundles."
        )
    if "Invalid result.json" in message or "Unsupported failed-run schema" in message:
        return (
            "The artifact schema is unsupported or corrupt. Validate the source "
            "bundle and schema version before importing."
        )
    return (
        "Import validates manifest, checksums, safe paths, schema markers, and "
        "duplicate run IDs before copying evidence."
    )


def _telemetry_history_error_hint(message: str) -> str:
    if "Orchestrator telemetry feed" in message:
        return (
            "Attach only EdgeEnv runtime telemetry feed artifacts produced by "
            "InferEdgeOrchestrator for run IDs included in this export. The feed "
            "is supplemental operation context and never replaces runtime telemetry."
        )
    if "Run not found" in message:
        return (
            "Use `edgeenv runs list` to find registered run IDs, or omit "
            "--run-id to export history for all registered runs."
        )
    if "Invalid result artifact" in message:
        return (
            "Runtime telemetry history is rebuilt from result.json artifacts. "
            "Re-import or re-run the affected benchmark before exporting history."
        )
    return (
        "Telemetry history export reads local result artifacts and optional "
        "runtime_telemetry evidence; missing telemetry is recorded as an evidence gap."
    )


def _telemetry_history_input_error_hint(message: str) -> str:
    if "No such file" in message:
        return (
            "Create a history artifact first with "
            "`edgeenv runs telemetry export-history --output <path>`."
        )
    return (
        "Pass a JSON artifact produced by "
        "`edgeenv runs telemetry export-history`; telemetry context remains "
        "supplemental and never bypasses comparability."
    )


def _export_error_hint(message: str) -> str:
    if "Required run artifact file missing" in message:
        return (
            "Export requires result/config/target/env/stdout/stderr evidence files. "
            "Re-run the benchmark or inspect the artifact directory."
        )
    if "Sampler raw artifact listed in metadata is missing" in message:
        return (
            "Sampler metadata lists a raw artifact that is absent. Re-run the "
            "sampled benchmark so metadata and raw artifacts stay together."
        )
    if "symlink" in message or "Unsafe export archive path" in message:
        return (
            "Export only packages regular files under the run artifact directory. "
            "Remove unsafe paths or symlinks before exporting."
        )
    return "Export reads artifact files from the local registry path and writes a zip bundle."


def _fail(message: str, *, hint: str | None = None) -> None:
    console.print(f"[red]Error:[/red] {message}", soft_wrap=True)
    if hint:
        console.print(f"[yellow]Hint:[/yellow] {hint}", soft_wrap=True)
    raise typer.Exit(code=1)


def main(args: Optional[list[str]] = None) -> None:
    app(args=args)


if __name__ == "__main__":
    main()
