from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from edgeenv import __version__
from edgeenv.compare.comparability import check_comparability
from edgeenv.config.bench_config import load_benchmark_config
from edgeenv.config.target_profile import TargetProfile, load_target_profile
from edgeenv.registry.db import RunRegistry
from edgeenv.result.writer import ResultArtifactWriter, build_run_result, load_result
from edgeenv.runners.fake import FakeRunner


app = typer.Typer(help="EdgeEnv benchmark runner and local result registry.")
profile_app = typer.Typer(help="Target profile commands.")
bench_app = typer.Typer(help="Benchmark config and run commands.")
runs_app = typer.Typer(help="Local run registry commands.")
report_app = typer.Typer(help="Report and comparison commands.")
console = Console()

app.add_typer(profile_app, name="profile")
app.add_typer(bench_app, name="bench")
app.add_typer(runs_app, name="runs")
app.add_typer(report_app, name="report")


@app.command()
def doctor() -> None:
    """Check that the EdgeEnv CLI is available."""
    console.print("[bold green]EdgeEnv doctor: OK[/bold green]")
    console.print(f"Version: {__version__}")
    console.print("Runner support: fake")
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
    runner_result = runner.run(config, target)
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
    console.print(f"Result: {result_path}")
    console.print(f"Latency mean: {result.metrics.latency_mean_ms} ms")


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
    console.print(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True))


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


def _runner_for_target(target: TargetProfile) -> FakeRunner:
    if target.target_type in {"fake", "local"}:
        return FakeRunner()
    _fail(f"Unsupported target_type for v1: {target.target_type}")


def _fail(message: str) -> None:
    console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(code=1)


def main(args: Optional[list[str]] = None) -> None:
    app(args=args)


if __name__ == "__main__":
    main()
