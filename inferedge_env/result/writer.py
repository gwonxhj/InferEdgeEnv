from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.result.schema import (
    BenchmarkMetrics,
    BenchmarkProtocol,
    FAILED_RUN_SCHEMA_VERSION,
    ModelIdentity,
    RunResult,
    RuntimeIdentity,
    TargetIdentity,
)
from inferedge_env.runners.base import RunnerResult
from inferedge_env.samplers.base import (
    SAMPLER_METADATA_SCHEMA_VERSION,
    SamplerSummary,
)
from inferedge_env.utils.hashing import stable_model_hash
from inferedge_env.utils.system_info import collect_system_info

SAMPLER_METADATA_REQUIRED_KEYS = {
    "schema_version",
    "sampler_name",
    "platform_tool",
    "sampling_scope",
    "benchmark_window",
    "sample_count",
    "raw_artifacts",
    "fields",
    "warnings",
}


class SamplerArtifactError(ValueError):
    """Raised when sampler evidence cannot be persisted safely."""


def new_run_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"run-{stamp}-{uuid.uuid4().hex[:8]}"


def build_run_result(
    config: BenchmarkConfig,
    target: TargetProfile,
    runner_result: RunnerResult,
    run_id: str | None = None,
    env: dict[str, Any] | None = None,
) -> RunResult:
    captured_env = env or collect_system_info()
    return RunResult(
        run_id=run_id or new_run_id(),
        created_at=datetime.now(timezone.utc),
        benchmark_name=config.name,
        command=config.command,
        model=ModelIdentity(
            model_name=config.model_name,
            model_version=config.model_version,
            model_format=config.model_format,
            model_path=config.model_path,
            model_hash=stable_model_hash(config.model_path),
        ),
        runtime=RuntimeIdentity(
            runtime=config.runtime,
            execution_provider=config.execution_provider,
        ),
        target=TargetIdentity(
            target_name=target.target_name,
            target_type=target.target_type,
            board_name=target.board_name,
            os=target.os,
            runtime_tags=target.runtime_tags,
        ),
        protocol=BenchmarkProtocol(
            input_shape=config.input_shape,
            input_dtype=config.input_dtype,
            task=config.task,
            precision=config.precision,
            batch_size=config.batch_size,
            warmup_runs=config.warmup_runs,
            repeat_runs=config.repeat_runs,
            include_preprocess=config.include_preprocess,
            include_postprocess=config.include_postprocess,
        ),
        metrics=BenchmarkMetrics(
            latency_mean_ms=runner_result.latency_mean_ms,
            latency_p50_ms=runner_result.latency_p50_ms,
            latency_p95_ms=runner_result.latency_p95_ms,
            latency_p99_ms=runner_result.latency_p99_ms,
            throughput_fps=runner_result.throughput_fps,
        ),
        resource_metrics=runner_result.resource_metrics,
        runtime_operation_summary=runner_result.runtime_operation_summary,
        env=captured_env,
    )


class ResultArtifactWriter:
    def __init__(self, root: Path | str = ".edgeenv") -> None:
        self.root = Path(root)

    def write(
        self,
        result: RunResult,
        config_path: Path | str,
        target_path: Path | str,
        stdout: str,
        stderr: str,
    ) -> Path:
        run_dir = self.root / "runs" / result.run_id
        _prepare_successful_run_dir(run_dir)

        payload = result.model_dump(mode="json")
        if payload["resource_metrics"] is None:
            del payload["resource_metrics"]
        else:
            payload["resource_metrics"] = {
                key: value
                for key, value in payload["resource_metrics"].items()
                if value is not None
            }
        if payload["runtime_operation_summary"] is None:
            del payload["runtime_operation_summary"]
        (run_dir / "result.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
        (run_dir / "config.yaml").write_text(
            Path(config_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (run_dir / "target.yaml").write_text(
            Path(target_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (run_dir / "env.json").write_text(
            json.dumps(result.env, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (run_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (run_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        return run_dir


def write_sampler_artifacts(
    run_dir: Path | str,
    sampler_summary: SamplerSummary,
) -> Path | None:
    """Persist optional sampler metadata under a successful run artifact directory."""

    if not sampler_summary.metadata:
        return None

    artifact_dir = Path(run_dir)
    if not artifact_dir.is_dir():
        raise SamplerArtifactError(f"Run artifact directory is missing: {artifact_dir}")
    sampler_dir = artifact_dir / "sampler"
    _validate_sampler_metadata(sampler_summary.metadata, artifact_dir)
    _validate_sampler_raw_artifacts(sampler_summary.raw_artifacts, artifact_dir)

    sampler_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = sampler_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(sampler_summary.metadata, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata_path


class FailedRunArtifactWriter:
    def __init__(self, root: Path | str = ".edgeenv") -> None:
        self.root = Path(root)

    def write(
        self,
        config: BenchmarkConfig,
        target: TargetProfile,
        config_path: Path | str,
        target_path: Path | str,
        error_message: str,
        stdout: str,
        stderr: str,
        return_code: int | None = None,
        run_id: str | None = None,
        env: dict[str, Any] | None = None,
    ) -> Path:
        failure_id = run_id or new_run_id()
        captured_env = env or collect_system_info()
        failed_dir = self.root / "failed-runs" / failure_id
        failed_dir.mkdir(parents=True, exist_ok=False)

        failure = {
            "schema_version": FAILED_RUN_SCHEMA_VERSION,
            "run_id": failure_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "benchmark_name": config.name,
            "target_name": target.target_name,
            "target_type": target.target_type,
            "command": config.command,
            "error_type": "LocalRunnerError",
            "error_message": error_message,
            "return_code": return_code,
        }
        (failed_dir / "failure.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (failed_dir / "config.yaml").write_text(
            Path(config_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (failed_dir / "target.yaml").write_text(
            Path(target_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (failed_dir / "env.json").write_text(
            json.dumps(captured_env, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        (failed_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (failed_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        return failed_dir


def load_result(path: Path | str) -> RunResult:
    return RunResult.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _prepare_successful_run_dir(run_dir: Path) -> None:
    if not run_dir.exists():
        run_dir.mkdir(parents=True, exist_ok=False)
        return
    sampler_dir = run_dir / "sampler"
    allowed = {sampler_dir}
    existing = set(run_dir.iterdir())
    if not existing <= allowed or (sampler_dir.exists() and not sampler_dir.is_dir()):
        raise FileExistsError(f"Run artifact directory already exists: {run_dir}")


def _validate_sampler_metadata(metadata: dict[str, Any], run_dir: Path) -> None:
    missing = sorted(SAMPLER_METADATA_REQUIRED_KEYS - metadata.keys())
    if missing:
        raise SamplerArtifactError(
            "Sampler metadata missing required keys: " + ", ".join(missing)
        )
    if metadata.get("schema_version") != SAMPLER_METADATA_SCHEMA_VERSION:
        raise SamplerArtifactError("Unsupported sampler metadata schema")
    raw_artifacts = metadata["raw_artifacts"]
    if not isinstance(raw_artifacts, list):
        raise SamplerArtifactError("Sampler metadata raw_artifacts must be a list")
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, str):
            raise SamplerArtifactError(
                "Sampler metadata raw_artifacts entries must be strings"
            )
        raw_path = _validate_sampler_relative_path(raw_artifact)
        expected_path = run_dir / Path(*raw_path.parts)
        if not expected_path.is_file():
            raise SamplerArtifactError(
                f"Sampler raw artifact listed in metadata is missing: {raw_artifact}"
            )


def _validate_sampler_relative_path(raw_artifact: str) -> PurePosixPath:
    raw_path = PurePosixPath(raw_artifact)
    if raw_path.is_absolute() or ".." in raw_path.parts:
        raise SamplerArtifactError(f"Unsafe sampler raw artifact path: {raw_artifact}")
    if not raw_path.parts or raw_path.parts[0] != "sampler":
        raise SamplerArtifactError(
            f"Sampler raw artifact must be under sampler/: {raw_artifact}"
        )
    if raw_path.name == "metadata.json":
        raise SamplerArtifactError(
            "Sampler metadata cannot list metadata.json as a raw artifact"
        )
    return raw_path


def _validate_sampler_raw_artifacts(raw_artifacts: list[Path], run_dir: Path) -> None:
    sampler_dir = run_dir / "sampler"
    for raw_artifact in raw_artifacts:
        path = Path(raw_artifact)
        if not path.is_file():
            raise SamplerArtifactError(f"Sampler raw artifact is missing: {path}")
        try:
            path.resolve().relative_to(sampler_dir.resolve())
        except ValueError as exc:
            raise SamplerArtifactError(
                f"Sampler raw artifact must be under {sampler_dir}: {path}"
            ) from exc
