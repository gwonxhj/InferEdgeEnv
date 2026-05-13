from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from inferedge_env.cli import app


REQUIRED_RUN_FILES = {
    "result.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
}
REQUIRED_FAILED_RUN_FILES = {
    "failure.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
}


def test_valid_local_evidence_contract_registers_artifacts_and_resources(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    bench_path, profile_path = _write_bench_and_profile(
        tmp_path,
        script_body=_metrics_script_body(
            latency_mean_ms=10.0,
            resource_metrics={
                "memory_peak_mb": 256.0,
                "power_mean_w": 6.5,
                "source": "conformance-script",
            },
        ),
    )

    result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            str(profile_path),
            "--config",
            str(bench_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0
    assert "Benchmark run stored" in result.output
    assert "Resource metrics: stored" in result.output
    run_id = _run_id_from_output(result.output)
    run_dir = edgeenv_root / "runs" / run_id
    assert {path.name for path in run_dir.iterdir()} >= REQUIRED_RUN_FILES
    assert not (edgeenv_root / "failed-runs").exists()

    result_payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert result_payload["metrics"]["latency_mean_ms"] == 10.0
    assert result_payload["resource_metrics"]["source"] == "conformance-script"
    assert "EDGEENV_RESOURCE_METRICS_JSON=" in (
        run_dir / "stdout.log"
    ).read_text(encoding="utf-8")

    resources = runner.invoke(
        app,
        [
            "runs",
            "resources",
            "list",
            "--json",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert resources.exit_code == 0
    resources_payload = json.loads(resources.output)
    assert resources_payload["note"].startswith("Resource metrics are supplemental")
    assert resources_payload["count"] == 2
    assert {
        (record["metric_name"], record["source"])
        for record in resources_payload["results"]
    } == {
        ("memory_peak_mb", "conformance-script"),
        ("power_mean_w", "conformance-script"),
    }


@pytest.mark.parametrize(
    ("script_body", "expected_error", "expected_stdout"),
    [
        (
            "print('no metrics here')\n",
            "Missing EDGEENV_METRICS_JSON",
            "no metrics here",
        ),
        (
            "print('EDGEENV_METRICS_JSON={bad json')\n",
            "Invalid EDGEENV_METRICS_JSON JSON",
            "EDGEENV_METRICS_JSON={bad json",
        ),
        (
            "\n".join(
                [
                    "print('EDGEENV_RESOURCE_METRICS_JSON={bad resource json')",
                    "print('EDGEENV_METRICS_JSON={\"latency_mean_ms\":1,\"latency_p50_ms\":1,\"latency_p95_ms\":1,\"latency_p99_ms\":1,\"throughput_fps\":1}')",
                ]
            )
            + "\n",
            "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON",
            "EDGEENV_RESOURCE_METRICS_JSON={bad resource json",
        ),
    ],
)
def test_corrupt_local_evidence_contract_writes_failed_run_without_registry(
    tmp_path: Path,
    script_body: str,
    expected_error: str,
    expected_stdout: str,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    bench_path, profile_path = _write_bench_and_profile(
        tmp_path,
        script_body=script_body,
    )

    result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            str(profile_path),
            "--config",
            str(bench_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 1
    assert expected_error in result.output
    assert "Failed run artifact:" in result.output
    assert "Registry: not updated" in result.output
    assert not (edgeenv_root / "runs.db").exists()
    assert not (edgeenv_root / "runs").exists()
    failed_dirs = list((edgeenv_root / "failed-runs").iterdir())
    assert len(failed_dirs) == 1
    failed_dir = failed_dirs[0]
    assert {path.name for path in failed_dir.iterdir()} == REQUIRED_FAILED_RUN_FILES

    failure = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["schema_version"] == "edgeenv.failed-run.v1"
    assert expected_error in failure["error_message"]
    assert failure["return_code"] == 0
    assert expected_stdout in (failed_dir / "stdout.log").read_text(encoding="utf-8")


def test_compare_judgement_is_preserved_after_successful_export_import(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    source_root = tmp_path / "source" / ".edgeenv"
    imported_root = tmp_path / "imported" / ".edgeenv"
    same_a = _run_local_benchmark(
        runner,
        tmp_path,
        source_root,
        name="same-a",
        latency_mean_ms=10.0,
    )
    same_b = _run_local_benchmark(
        runner,
        tmp_path,
        source_root,
        name="same-b",
        latency_mean_ms=12.0,
    )
    runtime_b = _run_local_benchmark(
        runner,
        tmp_path,
        source_root,
        name="runtime-b",
        latency_mean_ms=8.0,
        runtime="conformance-runtime-alt",
    )
    model_b = _run_local_benchmark(
        runner,
        tmp_path,
        source_root,
        name="model-b",
        latency_mean_ms=7.0,
        model_path="models/conformance-other.onnx",
    )

    _assert_same_condition_compare(
        _compare(runner, source_root, same_a, same_b),
    )
    _assert_conditional_runtime_compare(
        _compare(runner, source_root, same_a, runtime_b),
    )
    _assert_non_comparable_model_hash(
        _compare(runner, source_root, same_a, model_b),
    )

    for run_id in [same_a, same_b, runtime_b, model_b]:
        archive_path = tmp_path / "exports" / f"{run_id}.zip"
        export_result = runner.invoke(
            app,
            [
                "runs",
                "export",
                run_id,
                "--output",
                str(archive_path),
                "--edgeenv-root",
                str(source_root),
            ],
        )
        assert export_result.exit_code == 0
        import_result = runner.invoke(
            app,
            [
                "runs",
                "import",
                str(archive_path),
                "--edgeenv-root",
                str(imported_root),
            ],
        )
        assert import_result.exit_code == 0

    _assert_same_condition_compare(
        _compare(runner, imported_root, same_a, same_b),
    )
    _assert_conditional_runtime_compare(
        _compare(runner, imported_root, same_a, runtime_b),
    )
    _assert_non_comparable_model_hash(
        _compare(runner, imported_root, same_a, model_b),
    )


def _run_local_benchmark(
    runner: CliRunner,
    tmp_path: Path,
    edgeenv_root: Path,
    *,
    name: str,
    latency_mean_ms: float,
    runtime: str = "conformance-runtime",
    model_path: str = "models/conformance.onnx",
) -> str:
    bench_path, profile_path = _write_bench_and_profile(
        tmp_path / name,
        script_body=_metrics_script_body(latency_mean_ms=latency_mean_ms),
        name=name,
        runtime=runtime,
        model_path=model_path,
    )
    result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            str(profile_path),
            "--config",
            str(bench_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    assert result.exit_code == 0, result.output
    return _run_id_from_output(result.output)


def _write_bench_and_profile(
    root: Path,
    *,
    script_body: str,
    name: str = "conformance",
    runtime: str = "conformance-runtime",
    model_path: str = "models/conformance.onnx",
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    script = root / f"{name}_bench.py"
    script.write_text(script_body, encoding="utf-8")
    bench_path = root / f"{name}_bench.yaml"
    profile_path = root / f"{name}_profile.yaml"
    bench_path.write_text(
        f"""
name: {name}
command: {shlex.quote(sys.executable)} {shlex.quote(str(script))}
model_name: conformance-model
model_version: "1.0"
model_format: onnx
model_path: {model_path}
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: {runtime}
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: true
include_postprocess: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    profile_path.write_text(
        """
target_name: conformance-local
target_type: local
board_name: local-dev-machine
os: test-os
runtime_tags: [local, conformance]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return bench_path, profile_path


def _metrics_script_body(
    *,
    latency_mean_ms: float,
    resource_metrics: dict[str, object] | None = None,
) -> str:
    lines = [
        "import json",
        "print('conformance benchmark log')",
    ]
    if resource_metrics is not None:
        lines.append(
            "print('EDGEENV_RESOURCE_METRICS_JSON=' + "
            f"json.dumps({resource_metrics!r}))"
        )
    metrics = {
        "latency_mean_ms": latency_mean_ms,
        "latency_p50_ms": latency_mean_ms - 0.5,
        "latency_p95_ms": latency_mean_ms + 1.0,
        "latency_p99_ms": latency_mean_ms + 2.0,
        "throughput_fps": round(1000.0 / latency_mean_ms, 6),
    }
    lines.append("print('EDGEENV_METRICS_JSON=' + " f"json.dumps({metrics!r}))")
    return "\n".join(lines) + "\n"


def _compare(
    runner: CliRunner,
    edgeenv_root: Path,
    run_id_a: str,
    run_id_b: str,
) -> str:
    result = runner.invoke(
        app,
        [
            "report",
            "compare",
            run_id_a,
            run_id_b,
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    assert result.exit_code == 0, result.output
    return result.output


def _assert_same_condition_compare(output: str) -> None:
    assert "Comparable: Yes" in output
    assert "Mode: same-condition" in output
    assert "- Same model hash" in output
    assert "- Same benchmark protocol" in output
    assert "Metrics Delta:" in output


def _assert_conditional_runtime_compare(output: str) -> None:
    assert "Comparable: Conditional" in output
    assert "Mode: runtime-comparison" in output
    assert "- Different runtime or execution provider" in output
    assert "Metrics Delta:" not in output


def _assert_non_comparable_model_hash(output: str) -> None:
    assert "Comparable: No" in output
    assert "- Different model hash" in output
    assert "Metrics Delta:" not in output


def _run_id_from_output(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("Run ID: "):
            return line.removeprefix("Run ID: ").strip()
    raise AssertionError(f"Run ID not found in output:\n{output}")
