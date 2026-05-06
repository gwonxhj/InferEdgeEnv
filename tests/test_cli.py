from __future__ import annotations

import json
import shlex
import sys

from typer.testing import CliRunner

from inferedge_env.cli import app


def test_cli_doctor():
    runner = CliRunner()

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "EdgeEnv doctor: OK" in result.output


def test_cli_bench_run_with_fake_profile(tmp_path, config_files):
    runner = CliRunner()
    bench_path, profile_path = config_files
    edgeenv_root = tmp_path / ".edgeenv"

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
    assert (edgeenv_root / "runs.db").is_file()
    run_dirs = list((edgeenv_root / "runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "result.json").is_file()


def test_cli_bench_run_with_local_profile(tmp_path):
    runner = CliRunner()
    script = tmp_path / "local_bench.py"
    script.write_text(
        """
import json
print("local cli smoke")
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bench_path = tmp_path / "bench.yaml"
    profile_path = tmp_path / "profile.yaml"
    bench_path.write_text(
        f"""
name: local-cli
command: {shlex.quote(sys.executable)} {shlex.quote(str(script))}
model_name: local-model
model_version: "1.0"
model_format: onnx
model_path: models/local.onnx
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
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
target_name: local-machine
target_type: local
board_name: local-dev-machine
os: test-os
runtime_tags: [local]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    edgeenv_root = tmp_path / ".edgeenv"

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
    assert "Latency mean: 10.0 ms" in result.output
    run_dirs = list((edgeenv_root / "runs").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "stdout.log").read_text(encoding="utf-8").startswith(
        "local cli smoke"
    )


def test_cli_runs_show_includes_resource_metrics_from_result_artifact(tmp_path):
    runner = CliRunner()
    script = tmp_path / "local_bench.py"
    script.write_text(
        """
import json
print("EDGEENV_RESOURCE_METRICS_JSON=" + json.dumps({
    "memory_peak_mb": 512.0,
    "power_mean_w": 8.2,
    "source": "benchmark-command",
}))
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bench_path = tmp_path / "bench.yaml"
    profile_path = tmp_path / "profile.yaml"
    bench_path.write_text(
        f"""
name: local-cli-resource
command: {shlex.quote(sys.executable)} {shlex.quote(str(script))}
model_name: local-model
model_version: "1.0"
model_format: onnx
model_path: models/local.onnx
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
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
target_name: local-machine
target_type: local
board_name: local-dev-machine
os: test-os
runtime_tags: [local]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    edgeenv_root = tmp_path / ".edgeenv"

    run_result = runner.invoke(
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

    assert run_result.exit_code == 0
    run_dirs = list((edgeenv_root / "runs").iterdir())
    payload = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    show_result = runner.invoke(
        app,
        [
            "runs",
            "show",
            payload["run_id"],
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)
    assert shown["resource_metrics"]["memory_peak_mb"] == 512.0
    assert shown["resource_metrics"]["power_mean_w"] == 8.2
    assert shown["resource_metrics"]["source"] == "benchmark-command"


def test_cli_resource_metrics_example_run_and_show(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"

    run_result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_resource_metrics.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 12.8 ms" in run_result.output
    run_dirs = list((edgeenv_root / "runs").iterdir())
    payload = json.loads((run_dirs[0] / "result.json").read_text(encoding="utf-8"))
    assert payload["resource_metrics"]["memory_peak_mb"] == 512.0
    assert payload["resource_metrics"]["source"] == "example-script"
    show_result = runner.invoke(
        app,
        [
            "runs",
            "show",
            payload["run_id"],
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)
    assert shown["resource_metrics"]["power_peak_w"] == 11.4
    assert shown["resource_metrics"]["temperature_peak_c"] == 72.0


def test_cli_sampler_wrapper_example_run_and_show(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"

    run_result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_sampler_wrapper.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 12.3 ms" in run_result.output
    run_dirs = list((edgeenv_root / "runs").iterdir())
    run_dir = run_dirs[0]
    stdout = (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert "local benchmark smoke" in stdout
    assert "sampler-wrapper command=" in stdout
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["metrics"]["latency_mean_ms"] == 12.3
    assert payload["resource_metrics"]["memory_peak_mb"] == 384.0
    assert payload["resource_metrics"]["source"] == "deterministic-wrapper-demo"
    show_result = runner.invoke(
        app,
        [
            "runs",
            "show",
            payload["run_id"],
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)
    assert shown["resource_metrics"]["power_peak_w"] == 9.0
    assert shown["resource_metrics"]["temperature_peak_c"] == 68.0


def test_cli_sampler_unavailable_example_stores_run_without_resource_metrics(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"

    run_result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_sampler_unavailable.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 12.3 ms" in run_result.output
    run_dirs = list((edgeenv_root / "runs").iterdir())
    run_dir = run_dirs[0]
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert "resource_metrics" not in payload
    assert "sampler unavailable; resource metrics omitted" in (
        run_dir / "stderr.log"
    ).read_text(encoding="utf-8")
    assert (edgeenv_root / "runs.db").is_file()
    assert not (edgeenv_root / "failed-runs").exists()


def test_cli_malformed_sampler_resource_metrics_writes_failed_run_artifact(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"

    result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_sampler_malformed_resource.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 1
    assert "Failed run artifact:" in result.output
    assert "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON" in result.output
    assert not (edgeenv_root / "runs.db").exists()
    failed_dirs = list((edgeenv_root / "failed-runs").iterdir())
    assert len(failed_dirs) == 1
    failed_dir = failed_dirs[0]
    stdout = (failed_dir / "stdout.log").read_text(encoding="utf-8")
    assert "EDGEENV_RESOURCE_METRICS_JSON={bad sampler json" in stdout
    assert "EDGEENV_METRICS_JSON=" in stdout
    failure = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["return_code"] == 0
    assert "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON" in failure["error_message"]


def test_cli_local_failure_writes_failed_run_artifact(tmp_path):
    runner = CliRunner()
    script = tmp_path / "local_fail.py"
    script.write_text(
        """
import sys
print("before failure")
print("failure details", file=sys.stderr)
sys.exit(7)
""".strip()
        + "\n",
        encoding="utf-8",
    )
    bench_path = tmp_path / "bench.yaml"
    profile_path = tmp_path / "profile.yaml"
    bench_path.write_text(
        f"""
name: local-cli-fail
command: {shlex.quote(sys.executable)} {shlex.quote(str(script))}
model_name: local-model
model_version: "1.0"
model_format: onnx
model_path: models/local.onnx
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
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
target_name: local-machine
target_type: local
board_name: local-dev-machine
os: test-os
runtime_tags: [local]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    edgeenv_root = tmp_path / ".edgeenv"

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
    assert "Failed run artifact:" in result.output
    assert not (edgeenv_root / "runs.db").exists()
    failed_dirs = list((edgeenv_root / "failed-runs").iterdir())
    assert len(failed_dirs) == 1
    assert (failed_dirs[0] / "stdout.log").read_text(encoding="utf-8") == (
        "before failure\n"
    )
    assert (failed_dirs[0] / "stderr.log").read_text(encoding="utf-8") == (
        "failure details\n"
    )
    failure = json.loads((failed_dirs[0] / "failure.json").read_text(encoding="utf-8"))
    assert failure["return_code"] == 7
    assert failure["error_message"] == "Local benchmark command failed with exit code 7"
