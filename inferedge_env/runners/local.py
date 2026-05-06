from __future__ import annotations

import json
import os
import shlex
import subprocess

from pydantic import ValidationError

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.runners.base import RunnerResult


METRICS_PREFIX = "EDGEENV_METRICS_JSON="
METRICS_NAME = "EDGEENV_METRICS_JSON"


class LocalRunnerError(RuntimeError):
    """Raised when a local benchmark command cannot produce valid metrics."""

    def __init__(
        self,
        message: str,
        stdout: str = "",
        stderr: str = "",
        return_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.return_code = return_code


class LocalRunner:
    """Run a local benchmark command and parse its explicit metrics contract."""

    def run(self, config: BenchmarkConfig, target: TargetProfile) -> RunnerResult:
        argv = shlex.split(config.command)
        if not argv:
            raise LocalRunnerError("Local benchmark command is empty")

        env = os.environ.copy()
        env.update(_edgeenv_env(config, target))

        try:
            completed = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
        except OSError as exc:
            raise LocalRunnerError(f"Failed to start local benchmark command: {exc}") from exc

        if completed.returncode != 0:
            raise LocalRunnerError(
                f"Local benchmark command failed with exit code {completed.returncode}",
                stdout=completed.stdout,
                stderr=completed.stderr,
                return_code=completed.returncode,
            )

        try:
            metrics = _extract_metrics(completed.stdout)
        except LocalRunnerError as exc:
            raise LocalRunnerError(
                str(exc),
                stdout=completed.stdout,
                stderr=completed.stderr,
                return_code=completed.returncode,
            ) from exc
        return RunnerResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            **metrics,
        )


def _extract_metrics(stdout: str) -> dict[str, float]:
    metrics_line: str | None = None
    for line in stdout.splitlines():
        if line.startswith(METRICS_PREFIX):
            metrics_line = line[len(METRICS_PREFIX) :]

    if metrics_line is None:
        raise LocalRunnerError(f"Missing {METRICS_NAME}=<json> line in stdout")

    try:
        payload = json.loads(metrics_line)
    except json.JSONDecodeError as exc:
        raise LocalRunnerError(f"Invalid {METRICS_NAME} JSON: {exc}") from exc

    try:
        result = RunnerResult.model_validate({**payload, "stdout": "", "stderr": ""})
    except ValidationError as exc:
        raise LocalRunnerError(f"Invalid local metrics schema: {exc}") from exc

    return result.model_dump(exclude={"stdout", "stderr"})


def _edgeenv_env(config: BenchmarkConfig, target: TargetProfile) -> dict[str, str]:
    return {
        "EDGEENV_BENCHMARK_NAME": config.name,
        "EDGEENV_MODEL_NAME": config.model_name,
        "EDGEENV_MODEL_PATH": config.model_path,
        "EDGEENV_RUNTIME": config.runtime,
        "EDGEENV_EXECUTION_PROVIDER": config.execution_provider,
        "EDGEENV_PRECISION": config.precision,
        "EDGEENV_BATCH_SIZE": str(config.batch_size),
        "EDGEENV_WARMUP_RUNS": str(config.warmup_runs),
        "EDGEENV_REPEAT_RUNS": str(config.repeat_runs),
        "EDGEENV_INCLUDE_PREPROCESS": str(config.include_preprocess).lower(),
        "EDGEENV_INCLUDE_POSTPROCESS": str(config.include_postprocess).lower(),
        "EDGEENV_TARGET_NAME": target.target_name,
    }
