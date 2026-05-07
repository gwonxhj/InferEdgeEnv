from __future__ import annotations

import json
import shlex
import sys
import zipfile
from pathlib import Path

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
    assert "Resource metrics: omitted" in result.output
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
    assert "Resource metrics: omitted" in result.output
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
    assert (
        "Resource metrics: stored "
        "(source=benchmark-command, fields=memory_peak_mb, power_mean_w)"
    ) in run_result.output
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


def test_cli_runs_export_creates_evidence_zip(tmp_path, config_files):
    runner = CliRunner()
    bench_path, profile_path = config_files
    edgeenv_root = tmp_path / ".edgeenv"
    export_path = tmp_path / "exports" / "run.zip"

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
    run_dir = next((edgeenv_root / "runs").iterdir())
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    export_result = runner.invoke(
        app,
        [
            "runs",
            "export",
            payload["run_id"],
            "--output",
            str(export_path),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert export_result.exit_code == 0
    assert "Run evidence exported" in export_result.output
    assert payload["run_id"] in export_result.output
    assert export_path.is_file()
    with zipfile.ZipFile(export_path) as archive:
        names = set(archive.namelist())
        assert f"{payload['run_id']}/manifest.json" in names
        assert f"{payload['run_id']}/result.json" in names
        manifest = json.loads(archive.read(f"{payload['run_id']}/manifest.json"))
    assert manifest["schema_version"] == "edgeenv.export.v1"
    assert manifest["bundle_type"] == "successful-run"
    assert manifest["run_id"] == payload["run_id"]
    assert sorted(entry["path"] for entry in manifest["files"]) == [
        "config.yaml",
        "env.json",
        "result.json",
        "stderr.log",
        "stdout.log",
        "target.yaml",
    ]


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
    assert "Resource metrics: stored (source=example-script" in run_result.output
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


def test_cli_local_template_example_run_and_show(tmp_path):
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
            "examples/benches/local_template.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 21.4 ms" in run_result.output
    assert "Resource metrics: stored (source=local-template" in run_result.output
    run_dirs = list((edgeenv_root / "runs").iterdir())
    run_dir = run_dirs[0]
    stdout = (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert "benchmark=local-template" in stdout
    assert "model=template-model" in stdout
    assert "target=local-machine" in stdout
    assert "template_mode=copy-me" in stdout
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["metrics"]["latency_mean_ms"] == 21.4
    assert payload["resource_metrics"]["memory_peak_mb"] == 256.0
    assert payload["resource_metrics"]["source"] == "local-template"


def test_cli_local_runtime_adapter_example_run_and_show(tmp_path):
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
            "examples/benches/local_runtime_adapter.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert run_result.exit_code == 0
    assert "Latency mean: 18.5 ms" in run_result.output
    assert "Resource metrics: stored (source=local-runtime-adapter-demo" in (
        run_result.output
    )
    run_dirs = list((edgeenv_root / "runs").iterdir())
    run_dir = run_dirs[0]
    stdout = (run_dir / "stdout.log").read_text(encoding="utf-8")
    assert "adapter=local-runtime-adapter-demo" in stdout
    assert "runtime_command_exit=0" in stdout
    assert "runtime_stdout=runtime-demo-inference" in stdout
    payload = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert payload["benchmark_name"] == "local-runtime-adapter-demo"
    assert payload["metrics"]["latency_mean_ms"] == 18.5
    assert payload["metrics"]["throughput_fps"] == 54.1
    assert payload["resource_metrics"]["memory_peak_mb"] == 216.0
    assert payload["resource_metrics"]["source"] == "local-runtime-adapter-demo"
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
    assert shown["runtime"]["runtime"] == "python-subprocess"
    assert shown["resource_metrics"]["memory_mean_mb"] == 204.0


def test_cli_compare_workflow_examples_same_condition(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"

    first = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_compare_a.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    second = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_compare_b.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert first.exit_code == 0
    assert "Latency mean: 18.0 ms" in first.output
    assert second.exit_code == 0
    assert "Latency mean: 16.4 ms" in second.output

    run_dirs = sorted((edgeenv_root / "runs").iterdir())
    payloads = [
        json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        for run_dir in run_dirs
    ]
    run_id_a = next(
        payload["run_id"]
        for payload in payloads
        if payload["benchmark_name"] == "local-compare-a"
    )
    run_id_b = next(
        payload["run_id"]
        for payload in payloads
        if payload["benchmark_name"] == "local-compare-b"
    )

    list_result = runner.invoke(
        app,
        ["runs", "list", "--edgeenv-root", str(edgeenv_root)],
    )
    show_result = runner.invoke(
        app,
        ["runs", "show", run_id_a, "--edgeenv-root", str(edgeenv_root)],
    )
    compare_result = runner.invoke(
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

    assert list_result.exit_code == 0
    assert "EdgeEnv Runs" in list_result.output
    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)
    assert shown["metrics"]["latency_mean_ms"] == 18.0
    assert compare_result.exit_code == 0
    assert "Comparable: Yes" in compare_result.output
    assert "Mode: same-condition" in compare_result.output
    assert "- Same benchmark protocol" in compare_result.output
    mode_index = compare_result.output.index("Mode: same-condition")
    delta_index = compare_result.output.index("Metrics Delta:")
    assert mode_index < delta_index
    assert "Metrics Delta:" in compare_result.output
    assert (
        "- latency_mean_ms: 18.0 ms -> 16.4 ms "
        "(delta -1.6 ms, -8.89%)"
    ) in compare_result.output
    assert (
        "- throughput_fps: 55.5 fps -> 61.0 fps "
        "(delta +5.5 fps, +9.91%)"
    ) in compare_result.output


def test_cli_compare_runtime_difference_suppresses_metric_delta(tmp_path):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    runtime_config = tmp_path / "local_compare_b_runtime.yaml"
    runtime_config.write_text(
        Path("examples/benches/local_compare_b.yaml")
        .read_text(encoding="utf-8")
        .replace("runtime: local-python", "runtime: local-python-alt"),
        encoding="utf-8",
    )

    first = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            "examples/benches/local_compare_a.yaml",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    second = runner.invoke(
        app,
        [
            "bench",
            "run",
            "--target",
            "examples/profiles/local.yaml",
            "--config",
            str(runtime_config),
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert first.exit_code == 0
    assert second.exit_code == 0
    payloads = [
        json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        for run_dir in sorted((edgeenv_root / "runs").iterdir())
    ]
    run_id_a = next(
        payload["run_id"]
        for payload in payloads
        if payload["benchmark_name"] == "local-compare-a"
    )
    run_id_b = next(
        payload["run_id"]
        for payload in payloads
        if payload["benchmark_name"] == "local-compare-b"
    )

    compare_result = runner.invoke(
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

    assert compare_result.exit_code == 0
    assert "Comparable: Conditional" in compare_result.output
    assert "Mode: runtime-comparison" in compare_result.output
    assert "- Different runtime or execution provider" in compare_result.output
    assert "Metrics Delta:" not in compare_result.output


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
    assert (
        "Resource metrics: stored (source=deterministic-wrapper-demo"
        in run_result.output
    )
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
    assert "Resource metrics: omitted" in run_result.output
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
    assert "Registry: not updated" in result.output
    assert "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON" in result.output
    assert not (edgeenv_root / "runs.db").exists()
    failed_dirs = list((edgeenv_root / "failed-runs").iterdir())
    assert len(failed_dirs) == 1
    failed_dir = failed_dirs[0]
    stdout = (failed_dir / "stdout.log").read_text(encoding="utf-8")
    assert "EDGEENV_RESOURCE_METRICS_JSON={bad sampler json" in stdout
    assert "EDGEENV_METRICS_JSON=" in stdout
    failure = json.loads((failed_dir / "failure.json").read_text(encoding="utf-8"))
    assert failure["schema_version"] == "edgeenv.failed-run.v1"
    assert failure["return_code"] == 0
    assert "Invalid EDGEENV_RESOURCE_METRICS_JSON JSON" in failure["error_message"]
    assert (failed_dir / "config.yaml").is_file()
    assert (failed_dir / "target.yaml").is_file()
    assert (failed_dir / "env.json").is_file()


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
    assert "Registry: not updated" in result.output
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
    assert failure["schema_version"] == "edgeenv.failed-run.v1"
    assert failure["return_code"] == 7
    assert failure["error_message"] == "Local benchmark command failed with exit code 7"
    assert (failed_dirs[0] / "config.yaml").is_file()
    assert (failed_dirs[0] / "target.yaml").is_file()
    assert (failed_dirs[0] / "env.json").is_file()

    list_result = runner.invoke(
        app,
        ["failed-runs", "list", "--edgeenv-root", str(edgeenv_root)],
    )
    show_result = runner.invoke(
        app,
        [
            "failed-runs",
            "show",
            failure["run_id"],
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )
    show_without_logs = runner.invoke(
        app,
        [
            "failed-runs",
            "show",
            failure["run_id"],
            "--edgeenv-root",
            str(edgeenv_root),
            "--log-chars",
            "0",
        ],
    )

    assert list_result.exit_code == 0
    assert "EdgeEnv Failed Runs" in list_result.output
    assert failure["run_id"] in list_result.output
    assert "local-cli-fail" in list_result.output
    assert "Local benchmark command failed with exit code 7" in list_result.output
    assert show_result.exit_code == 0
    shown = json.loads(show_result.output)
    assert shown["failure"]["run_id"] == failure["run_id"]
    assert shown["failure"]["schema_version"] == "edgeenv.failed-run.v1"
    assert shown["failure"]["return_code"] == 7
    assert shown["stdout"] == "before failure\n"
    assert shown["stderr"] == "failure details\n"
    assert shown["files"]["failure"].endswith("failure.json")
    assert shown["files"]["stdout"].endswith("stdout.log")
    assert show_without_logs.exit_code == 0
    shown_without_logs = json.loads(show_without_logs.output)
    assert shown_without_logs["stdout"] == ""
    assert shown_without_logs["stderr"] == ""


def test_cli_failed_runs_show_rejects_path_like_id(tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "failed-runs",
            "show",
            "../not-a-run",
            "--edgeenv-root",
            str(tmp_path / ".edgeenv"),
        ],
    )

    assert result.exit_code == 1
    assert "Invalid failed run id: ../not-a-run" in result.output
