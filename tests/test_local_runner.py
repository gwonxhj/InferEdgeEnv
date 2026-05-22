from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from inferedge_env.config.target_profile import SamplerProfile
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.runners.local import LocalRunner, LocalRunnerError
from inferedge_env.samplers.base import SamplerSummary


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


def test_local_runner_disabled_sampler_preserves_current_behavior(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
import json
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local", "sampler": None})

    result = LocalRunner().run(config, target)

    assert result.latency_mean_ms == 10.0
    assert result.resource_metrics is None
    assert "EDGEENV_METRICS_JSON=" in result.stdout
    assert result.stderr == ""


def test_local_runner_recoverable_sampler_failure_preserves_primary_run(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_metrics_script(tmp_path)
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(
        update={
            "target_type": "local",
            "sampler": SamplerProfile(
                name="jetson-tegrastats",
                tegrastats_path="missing-tegrastats-for-test",
                required=False,
            ),
        }
    )

    result = LocalRunner().run(
        config,
        target,
        run_id="run-sampler-recoverable",
        artifact_dir=tmp_path / "run-sampler-recoverable",
    )

    assert result.latency_mean_ms == 10.0
    assert result.resource_metrics is None
    assert result.sampler_summary is not None
    assert result.sampler_summary.metadata["sample_count"] == 0
    assert "tegrastats unavailable" in result.sampler_summary.warnings[0]


def test_local_runner_required_sampler_failure_fails_before_command(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_metrics_script(tmp_path)
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(
        update={
            "target_type": "local",
            "sampler": SamplerProfile(
                name="jetson-tegrastats",
                tegrastats_path="missing-tegrastats-for-test",
                required=True,
            ),
        }
    )

    with pytest.raises(LocalRunnerError, match="Required sampler failed") as exc_info:
        LocalRunner().run(
            config,
            target,
            run_id="run-sampler-required",
            artifact_dir=tmp_path / "run-sampler-required",
        )

    assert exc_info.value.stdout == ""
    assert exc_info.value.stderr == ""


def test_local_runner_sampler_metrics_take_precedence_over_stdout_resource_metrics(
    tmp_path: Path,
    bench_config,
    target_profile,
    monkeypatch,
):
    class FakeSampler:
        name = "fake-sampler"

        def start(self, context):
            raw_log = context.artifact_dir / "sampler" / "tegrastats.log"
            raw_log.parent.mkdir(parents=True)
            raw_log.write_text("RAM 100/7620MB\n", encoding="utf-8")

        def stop(self):
            return None

        def summary(self):
            return SamplerSummary(
                resource_metrics=ResourceMetrics(
                    memory_peak_mb=100.0,
                    source="jetson-tegrastats",
                ),
                metadata={
                    "schema_version": "edgeenv.sampler-metadata.v1",
                    "sampler_name": "jetson-tegrastats",
                    "platform_tool": "tegrastats",
                    "sampling_scope": "host",
                    "benchmark_window": "sampler-start-before-command-stop-after-command",
                    "sample_count": 1,
                    "raw_artifacts": ["sampler/tegrastats.log"],
                    "fields": {},
                    "warnings": [],
                },
                raw_artifacts=[],
                warnings=[],
            )

    monkeypatch.setattr(
        "inferedge_env.runners.local.build_sampler",
        lambda profile: FakeSampler(),
    )
    script = _write_script(
        tmp_path,
        """
import json
print("EDGEENV_RESOURCE_METRICS_JSON=" + json.dumps({
    "memory_peak_mb": 999.0,
    "source": "benchmark-command",
}))
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(
        update={
            "target_type": "local",
            "sampler": SamplerProfile(
                name="jetson-tegrastats",
                interval_ms=50,
                startup_wait_ms=0,
            ),
        }
    )
    artifact_dir = tmp_path / "run-sampler-precedence"

    result = LocalRunner().run(
        config,
        target,
        run_id="run-sampler-precedence",
        artifact_dir=artifact_dir,
    )

    assert result.resource_metrics is not None
    assert result.resource_metrics.source == "jetson-tegrastats"
    assert result.resource_metrics.memory_peak_mb == 100.0
    assert result.sampler_summary is not None
    assert result.sampler_summary.metadata["raw_artifacts"] == ["sampler/tegrastats.log"]
    assert (artifact_dir / "sampler" / "tegrastats.log").is_file()


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


def test_local_runner_parses_optional_resource_metrics(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
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
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.resource_metrics is not None
    assert result.resource_metrics.memory_peak_mb == 512.0
    assert result.resource_metrics.power_mean_w == 8.2
    assert result.resource_metrics.source == "benchmark-command"


def test_local_runner_parses_optional_runtime_operation_summary(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
import json
print("EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON=" + json.dumps({
    "source": "inferedge-runtime",
    "health_reason": "completed",
    "runtime_events": [
        {
            "event": "runtime_operation_summary_recorded",
            "severity": "info",
        }
    ],
}))
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.runtime_operation_summary is not None
    assert result.runtime_operation_summary["source"] == "inferedge-runtime"
    assert (
        result.runtime_operation_summary["runtime_events"][0]["event"]
        == "runtime_operation_summary_recorded"
    )


def test_local_runner_parses_optional_runtime_telemetry(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
import json
print("EDGEENV_RUNTIME_TELEMETRY_JSON=" + json.dumps({
    "schema_version": "inferedge-runtime-telemetry-v1",
    "evidence_role": "runtime_telemetry_seed",
    "collection_mode": "single_result_export",
    "resource": {
        "telemetry_source": "runtime-result",
    },
}))
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.runtime_telemetry is not None
    assert result.runtime_telemetry["schema_version"] == (
        "inferedge-runtime-telemetry-v1"
    )
    assert result.runtime_telemetry["resource"]["telemetry_source"] == "runtime-result"


def test_local_runner_uses_last_resource_metrics_line(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":1}')
print('EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":2}')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":2,"latency_p50_ms":2,"latency_p95_ms":2,"latency_p99_ms":2,"throughput_fps":2}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert result.resource_metrics is not None
    assert result.resource_metrics.memory_peak_mb == 2.0


def test_local_runner_uses_working_directory_and_extra_env(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    script = _write_script(
        tmp_path,
        """
import json
import os
from pathlib import Path
Path("cwd-marker.txt").write_text(os.environ["LOCAL_FLAG"], encoding="utf-8")
print("cwd=" + Path.cwd().name)
print("flag=" + os.environ["LOCAL_FLAG"])
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 3.0,
    "latency_p50_ms": 3.0,
    "latency_p95_ms": 3.0,
    "latency_p99_ms": 3.0,
    "throughput_fps": 3.0,
}))
""",
    )
    config = bench_config.model_copy(
        update={
            "command": _python_command(script),
            "working_directory": str(work_dir),
            "extra_env": {"LOCAL_FLAG": "enabled"},
        }
    )
    target = target_profile.model_copy(update={"target_type": "local"})

    result = LocalRunner().run(config, target)

    assert "cwd=work" in result.stdout
    assert "flag=enabled" in result.stdout
    assert (work_dir / "cwd-marker.txt").read_text(encoding="utf-8") == "enabled"


def test_local_runner_timeout_fails(tmp_path: Path, bench_config, target_profile):
    script = _write_script(
        tmp_path,
        """
import time
time.sleep(1)
""",
    )
    config = bench_config.model_copy(
        update={"command": _python_command(script), "timeout_seconds": 0.01}
    )
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="timed out after 0.01 seconds") as exc_info:
        LocalRunner().run(config, target)
    assert exc_info.value.return_code is None


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


def test_local_runner_invalid_resource_metrics_json_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RESOURCE_METRICS_JSON={bad json')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="Invalid EDGEENV_RESOURCE_METRICS_JSON JSON"):
        LocalRunner().run(config, target)


def test_local_runner_invalid_resource_metrics_schema_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":1,"extra":2}')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(LocalRunnerError, match="Invalid local resource metrics schema"):
        LocalRunner().run(config, target)


def test_local_runner_invalid_runtime_operation_summary_json_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON={bad json')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(
        LocalRunnerError,
        match="Invalid EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON JSON",
    ):
        LocalRunner().run(config, target)


def test_local_runner_invalid_runtime_operation_summary_schema_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON=[{"source":"inferedge-runtime"}]')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(
        LocalRunnerError,
        match="Invalid local runtime operation summary schema",
    ):
        LocalRunner().run(config, target)


def test_local_runner_invalid_runtime_telemetry_json_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RUNTIME_TELEMETRY_JSON={bad json')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(
        LocalRunnerError,
        match="Invalid EDGEENV_RUNTIME_TELEMETRY_JSON JSON",
    ):
        LocalRunner().run(config, target)


def test_local_runner_invalid_runtime_telemetry_schema_fails(
    tmp_path: Path,
    bench_config,
    target_profile,
):
    script = _write_script(
        tmp_path,
        """
print('EDGEENV_RUNTIME_TELEMETRY_JSON=[{"schema_version":"inferedge-runtime-telemetry-v1"}]')
print('EDGEENV_METRICS_JSON={"latency_mean_ms":1,"latency_p50_ms":1,"latency_p95_ms":1,"latency_p99_ms":1,"throughput_fps":1}')
""",
    )
    config = bench_config.model_copy(update={"command": _python_command(script)})
    target = target_profile.model_copy(update={"target_type": "local"})

    with pytest.raises(
        LocalRunnerError,
        match="Invalid local runtime telemetry schema",
    ):
        LocalRunner().run(config, target)


def _write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "local_bench.py"
    script.write_text(body.strip() + "\n", encoding="utf-8")
    return script


def _write_metrics_script(tmp_path: Path) -> Path:
    return _write_script(
        tmp_path,
        """
import json
print("EDGEENV_METRICS_JSON=" + json.dumps({
    "latency_mean_ms": 10.0,
    "latency_p50_ms": 9.5,
    "latency_p95_ms": 11.0,
    "latency_p99_ms": 12.0,
    "throughput_fps": 100.0,
}))
""",
    )


def _python_command(script: Path) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
