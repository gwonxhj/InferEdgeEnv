from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.table import Table

from inferedge_env import __version__
from inferedge_env.compare.comparability import check_comparability
from inferedge_env.config.bench_config import load_benchmark_config
from inferedge_env.config.target_profile import TargetProfile, load_target_profile
from inferedge_env.registry.db import RunRegistry
from inferedge_env.registry.models import RegistryRecord
from inferedge_env.result.exporter import (
    RunExportError,
    RunImportError,
    export_failed_run,
    export_successful_run,
    import_failed_run,
    import_successful_run,
    validate_successful_run_import,
)
from inferedge_env.result.schema import ResourceMetrics, RunResult
from inferedge_env.result.writer import (
    FailedRunArtifactWriter,
    ResultArtifactWriter,
    build_run_result,
    load_result,
)
from inferedge_env.runners.fake import FakeRunner
from inferedge_env.runners.local import LocalRunner, LocalRunnerError


app = typer.Typer(help="EdgeEnv benchmark runner and local result registry.")
profile_app = typer.Typer(help="Target profile commands.")
bench_app = typer.Typer(help="Benchmark config and run commands.")
runs_app = typer.Typer(help="Local run registry commands.")
failed_runs_app = typer.Typer(help="Failed local run artifact commands.")
report_app = typer.Typer(help="Report and comparison commands.")
console = Console()

app.add_typer(profile_app, name="profile")
app.add_typer(bench_app, name="bench")
app.add_typer(runs_app, name="runs")
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
        _fail(str(exc))
    console.print(f"[green]Valid target profile:[/green] {profile.target_name}")


@bench_app.command("validate")
def validate_bench(bench_config_path: Path) -> None:
    """Validate a benchmark config YAML file."""
    try:
        config = load_benchmark_config(bench_config_path)
    except ValueError as exc:
        _fail(str(exc))
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
        _fail(str(exc))

    runner = _runner_for_target(target)
    try:
        runner_result = runner.run(config, target)
    except LocalRunnerError as exc:
        failed_dir = FailedRunArtifactWriter(edgeenv_root).write(
            config=config,
            target=target,
            config_path=config_path,
            target_path=target_path,
            error_message=str(exc),
            stdout=exc.stdout,
            stderr=exc.stderr,
            return_code=exc.return_code,
        )
        console.print(
            f"[yellow]Failed run artifact:[/yellow] {failed_dir}",
            soft_wrap=True,
        )
        console.print("[yellow]Registry:[/yellow] not updated")
        _fail(str(exc))
    result = build_run_result(config, target, runner_result)
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result=result,
        config_path=config_path,
        target_path=target_path,
        stdout=runner_result.stdout,
        stderr=runner_result.stderr,
    )
    result_path = run_dir / "result.json"
    RunRegistry(edgeenv_root / "runs.db").insert(result, result_path)

    console.print("[bold green]Benchmark run stored[/bold green]")
    console.print(f"Run ID: {result.run_id}")
    console.print(f"Result: {result_path}", soft_wrap=True)
    console.print(f"Latency mean: {result.metrics.latency_mean_ms} ms")
    console.print(_resource_metrics_status(result.resource_metrics), soft_wrap=True)


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
        _fail(str(exc))
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
            _fail(f"Run already exists in registry: {plan.result.run_id}")
        result, run_dir = import_successful_run(archive_path, edgeenv_root)
        registry.insert(result, run_dir / "result.json")
    except (RunImportError, OSError) as exc:
        _fail(str(exc))
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
        _fail(str(exc))
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
        _fail(str(exc))
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
    return payload


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
    if payload.get("schema_version") != "edgeenv.failed-run.v1":
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


def _fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}", soft_wrap=True)
    raise typer.Exit(code=1)


def main(args: Optional[list[str]] = None) -> None:
    app(args=args)


if __name__ == "__main__":
    main()
