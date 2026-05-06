from __future__ import annotations

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
