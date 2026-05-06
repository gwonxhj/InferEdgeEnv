from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from inferedge_env.runners.local import LocalRunner, LocalRunnerError


def test_local_runner_valid_command_returns_metrics(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
import json
import os
print("benchmark log")
print("target=" + os.environ["EDGEENV_TARGET_NAME"])
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )
    config = bench_config.model_copy(
        update={"command": _python_command(script), "runtime": "local-python"}
    )
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.latency_mean_ms == 10.0
    assert result.latency_p99_ms == 12.0
    assert result.throughput_fps == 100.0
    assert "benchmark log" in result.stdout
    assert "target=local-fake" in result.stdout
    assert result.stderr == ""


def test_local_runner_uses_last_metrics_line(tmp_path: Path, bench_config, target_profile):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":2,"latency_p50_ms":2,"latency_p95_ms":2,"latency_p99_ms":2,"throughput_fps":2}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.latency_mean_ms == 2.0
    assert result.throughput_fps == 2.0


def test_local_runner_non_zero_command_fails(tmp_path: Path, bench_config, target_profile):
    script = _write_script(
        tmp_path,
        """
import sys
print("failed benchmark")
sys.exit(7)
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="exit code 7") as exc_info:
        LocalRunner().run(config, target)
    assert exc_info.value.stdout == "failed benchmark\n"
    assert exc_info.value.stderr == ""
    assert exc_info.value.return_code == 7


def test_local_runner_missing_metrics_line_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(tmp_path, "print('no metrics here')\n")
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="Missing EDGEENV_METRICS_JSON") as exc_info:
        LocalRunner().run(config, target)
    assert exc_info.value.stdout == "no metrics here\n"
    assert exc_info.value.return_code == 0


def test_local_runner_invalid_metrics_json_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(tmp_path, "print('EDGEENV_METRICS_JSON={bad json')\n")
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="Invalid EDGEENV_METRICS_JSON JSON"):
        LocalRunner().run(config, target)


def test_local_runner_invalid_metrics_schema_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="Invalid local metrics schema"):
        LocalRunner().run(config, target)


def _write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "local_bench.py"
    script.write_text(body.strip() + "\n", encoding="utf-8")
    return script


def _python_command(script: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
