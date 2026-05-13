from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from typer.testing import CliRunner

from inferedge_env.cli import app


def test_cli_adapter_template_example_run_and_show(tmp_path: Path) -> None:
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
            "examples/benches/local_adapter_template.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 19.2 ms" in run_result.output
    assert "Resource metrics: stored (source=adapter-template" in run_result.output
    run_dir = next((edgeenv_root / "runs").iterdir())
    stdout = (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert "adapter=copyable-local-adapter" in stdout
    assert "wrapped_stdout=adapter-template-runtime" in stdout
    assert "wrapped_command_exit=0" in stdout
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "local-adapter-template"
    assert payload["metrics"]["latency_mean_ms"] == 19.2
    assert payload["metrics"]["throughput_fps"] == 52.1
    assert payload["resource_metrics"]["memory_peak_mb"] == 384.0
    assert payload["resource_metrics"]["source"] == "adapter-template"


def test_cli_adapter_template_preserves_wrapped_command_failure(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    bench_path = tmp_path / "adapter-failure.yaml"
    bench_path.write_text(
        f"""
name: local-adapter-template-failure
command: python examples/scripts/adapter_template.py -- {shlex.quote(sys.executable)} -c "import sys; print('wrapped-failure'); sys.exit(9)"
model_name: adapter-template-model
model_version: "1.0"
model_format: onnx
model_path: models/adapter-template.onnx
task: image-classification
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: user-owned-runtime
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: false
include_postprocess: false
timeout_seconds: 30
working_directory: .
""".strip()
        + "\n",
        encoding="utf-8",
    )

    run_result = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            str(bench_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 1
    assert "Local benchmark command failed with exit code 9" in run_result.output
    assert "Registry: not updated" in run_result.output
    failed_dir = next((edgeenv_root / "failed-runs").iterdir())
    failure = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["return_code"] == 9
    stdout = (failed_dir / "stdout.log").read_text(encoding="utf-8")
    assert "wrapped_stdout=wrapped-failure" in stdout
    assert "wrapped_command_exit=9" in stdout
    assert "EDGEENV_METRICS_JSON=" not in stdout
