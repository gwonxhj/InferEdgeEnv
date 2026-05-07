from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from pydantic import ValidationError

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.runners.base import RunnerResult
from inferedge_env.samplers.base import (
    FatalSamplerError,
    RecoverableSamplerError,
    SamplerContext,
    SamplerSummary,
)
from inferedge_env.samplers.factory import build_sampler


METRICS_PREFIX = "EDGEENV_METRICS_JSON="
METRICS_NAME = "EDGEENV_METRICS_JSON"
RESOURCE_METRICS_PREFIX = "EDGEENV_RESOURCE_METRICS_JSON="
RESOURCE_METRICS_NAME = "EDGEENV_RESOURCE_METRICS_JSON"


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

    def run(
        self,
        config: BenchmarkConfig,
        target: TargetProfile,
        run_id: str | None = None,
        artifact_dir: Path | str | None = None,
    ) -> RunnerResult:
        argv = shlex.split(config.command)
        if not argv:
            raise LocalRunnerError("Local benchmark command is empty")

        env = os.environ.copy()
        env.update(_edgeenv_env(config, target))
        sampler = build_sampler(target.sampler)
        sampler_summary: SamplerSummary | None = None
        sampler_started = False
        sampler_stop_error: FatalSamplerError | None = None

        if sampler is not None:
            if run_id is None or artifact_dir is None:
                raise LocalRunnerError(
                    "Sampler-enabled local runs require run_id and artifact_dir"
                )
            try:
                sampler.start(
                    SamplerContext(
                        run_id=run_id,
                        benchmark_name=config.name,
                        target_name=target.target_name,
                        target_type=target.target_type,
                        command=argv,
                        artifact_dir=Path(artifact_dir),
                    )
                )
                sampler_started = True
            except FatalSamplerError as exc:
                raise LocalRunnerError(f"Required sampler failed: {exc}") from exc
            except RecoverableSamplerError:
                sampler_started = False

        try:
            completed = _run_command(argv, config, env)
        finally:
            if sampler_started and sampler is not None:
                try:
                    sampler.stop()
                except FatalSamplerError as exc:
                    sampler_stop_error = exc
                except RecoverableSamplerError:
                    pass

        if sampler_stop_error is not None:
            raise LocalRunnerError(
                f"Required sampler failed: {sampler_stop_error}",
                stdout=completed.stdout,
                stderr=completed.stderr,
                return_code=completed.returncode,
            ) from sampler_stop_error

        try:
            metrics = _extract_metrics(completed.stdout)
            resource_metrics = _extract_resource_metrics(completed.stdout)
            if sampler is not None:
                try:
                    sampler_summary = sampler.summary()
                except FatalSamplerError as exc:
                    raise LocalRunnerError(
                        f"Required sampler failed: {exc}",
                        stdout=completed.stdout,
                        stderr=completed.stderr,
                        return_code=completed.returncode,
                    ) from exc
                except RecoverableSamplerError:
                    sampler_summary = None
                if (
                    sampler_summary is not None
                    and sampler_summary.resource_metrics is not None
                ):
                    resource_metrics = sampler_summary.resource_metrics
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
            resource_metrics=resource_metrics,
            sampler_summary=sampler_summary,
            **metrics,
        )


def _run_command(
    argv: list[str],
    config: BenchmarkConfig,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            cwd=config.working_directory,
            timeout=config.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise LocalRunnerError(
            f"Local benchmark command timed out after {config.timeout_seconds} seconds",
            stdout=_decode_timeout_output(exc.stdout),
            stderr=_decode_timeout_output(exc.stderr),
            return_code=None,
        ) from exc
    except OSError as exc:
        raise LocalRunnerError(f"Failed to start local benchmark command: {exc}") from exc

    if completed.returncode != 0:
        raise LocalRunnerError(
            f"Local benchmark command failed with exit code {completed.returncode}",
            stdout=completed.stdout,
            stderr=completed.stderr,
            return_code=completed.returncode,
        )
    return completed


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

    return result.model_dump(
        exclude={"stdout", "stderr", "resource_metrics", "sampler_summary"}
    )


def _extract_resource_metrics(stdout: str) -> ResourceMetrics | None:
    metrics_line: str | None = None
    for line in stdout.splitlines():
        if line.startswith(RESOURCE_METRICS_PREFIX):
            metrics_line = line[len(RESOURCE_METRICS_PREFIX) :]

    if metrics_line is None:
        return None

    try:
        payload = json.loads(metrics_line)
    except json.JSONDecodeError as exc:
        raise LocalRunnerError(f"Invalid {RESOURCE_METRICS_NAME} JSON: {exc}") from exc

    try:
        return ResourceMetrics.model_validate(payload)
    except ValidationError as exc:
        raise LocalRunnerError(f"Invalid local resource metrics schema: {exc}") from exc


def _edgeenv_env(config: BenchmarkConfig, target: TargetProfile) -> dict[str, str]:
    env = dict(config.extra_env)
    env.update(
        {
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
    )
    return env


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
