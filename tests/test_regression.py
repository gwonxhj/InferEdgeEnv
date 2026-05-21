from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from inferedge_env.cli import app
from inferedge_env.compare.regression import analyze_regression
from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.result.writer import ResultArtifactWriter
from inferedge_env.runners.base import RunnerResult
from helpers import make_result


def test_regression_detects_same_condition_latency_and_resource_regression(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            memory_peak_mb=100.0,
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=118.0,
            p95=132.0,
            p99=171.6,
            fps=39.0,
            memory_peak_mb=140.0,
        ),
    )

    report = analyze_regression(baseline, candidate)

    assert report.comparable is True
    assert report.mode == "same-condition"
    assert report.regression_detected is True
    assert report.regression_type == "mixed"
    assert report.severity == "high"
    assert report.recommendation == "review_required"
    assert report.evidence["mean_delta_pct"] == 18.0
    assert report.evidence["p99_delta_pct"] == 32.0
    assert report.evidence["fps_delta_pct"] == -22.0
    assert report.evidence["memory_peak_delta_pct"] == 40.0
    triggered = {item["name"] for item in report.evidence["triggered_thresholds"]}
    assert "mean_latency_review" in triggered
    assert "p99_latency_high" in triggered
    assert "fps_drop_review" in triggered
    assert "memory_peak_warning" in triggered


def test_regression_suppresses_delta_for_protocol_mismatch(
    bench_config,
    target_profile,
):
    baseline = make_result(bench_config, target_profile, run_id="baseline")
    changed = bench_config.model_copy(update={"repeat_runs": 30})
    candidate = make_result(changed, target_profile, run_id="candidate")

    report = analyze_regression(baseline, candidate)

    assert report.comparable is False
    assert report.mode == "protocol_mismatch"
    assert report.regression_detected is False
    assert report.regression_type == "not_evaluated"
    assert report.recommendation == "rerun_with_matching_protocol"
    assert "Different repeat runs" in report.evidence["comparability_reasons"]


def test_regression_cli_writes_json_and_markdown_reports(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(mean=100.0, p95=120.0, p99=130.0, fps=50.0),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "candidate",
        _runner_result(mean=118.0, p95=132.0, p99=171.6, fps=39.0),
    )
    json_path = tmp_path / "regression.json"
    md_path = tmp_path / "regression.md"

    result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EdgeEnv Runtime Regression Report" in result.output
    assert "Comparable: true" in result.output
    assert "Mode: same-condition" in result.output
    assert "Regression detected: true" in result.output
    assert "Severity: high" in result.output
    assert "- mean_delta_pct: +18.0%" in result.output
    assert "p99_latency_high" in result.output
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["regression_detected"] is True
    assert payload["mode"] == "same-condition"
    assert payload["evidence"]["p99_delta_pct"] == 32.0
    markdown = md_path.read_text(encoding="utf-8")
    assert "# EdgeEnv Runtime Regression Report" in markdown
    assert "`review_required`" in markdown


def test_regression_cli_marks_runtime_comparison_not_evaluated(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(mean=100.0, p95=120.0, p99=130.0, fps=50.0),
    )
    changed = bench_config.model_copy(update={"runtime": "other-runtime"})
    _write_registered_run(
        edgeenv_root,
        changed,
        target_profile,
        "candidate",
        _runner_result(mean=118.0, p95=132.0, p99=171.6, fps=39.0),
    )

    result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Comparable: false" in result.output
    assert "Mode: runtime-comparison" in result.output
    assert "Regression detected: false" in result.output
    assert "Recommendation: review_as_runtime_comparison" in result.output
    assert "Regression Evidence: not evaluated" in result.output
    assert "mean_delta_pct" not in result.output


def _runner_result(
    *,
    mean: float,
    p95: float,
    p99: float,
    fps: float,
    memory_peak_mb: float | None = None,
) -> RunnerResult:
    return RunnerResult(
        latency_mean_ms=mean,
        latency_p50_ms=mean - 1.0,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        throughput_fps=fps,
        resource_metrics=(
            ResourceMetrics(memory_peak_mb=memory_peak_mb)
            if memory_peak_mb is not None
            else None
        ),
        stdout="stdout\n",
        stderr="",
    )


def _write_registered_run(
    edgeenv_root: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
    run_id: str,
    runner_result: RunnerResult,
) -> None:
    config_path = edgeenv_root.parent / f"{run_id}-config.yaml"
    target_path = edgeenv_root.parent / f"{run_id}-target.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("name: test\n", encoding="utf-8")
    target_path.write_text("target_name: test\n", encoding="utf-8")
    result = make_result(
        bench_config,
        target_profile,
        run_id=run_id,
        runner_result=runner_result,
    )
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result=result,
        config_path=config_path,
        target_path=target_path,
        stdout="stdout\n",
        stderr="stderr\n",
    )
    RunRegistry(edgeenv_root / "runs.db").insert(result, run_dir / "result.json")
