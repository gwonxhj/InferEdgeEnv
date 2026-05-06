from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edgeenv.config.bench_config import BenchmarkConfig
from edgeenv.config.target_profile import TargetProfile
from edgeenv.result.schema import (
    BenchmarkMetrics,
    BenchmarkProtocol,
    ModelIdentity,
    RunResult,
    RuntimeIdentity,
    TargetIdentity,
)
from edgeenv.runners.base import RunnerResult
from edgeenv.utils.hashing import stable_model_hash
from edgeenv.utils.system_info import collect_system_info


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
        run_dir.mkdir(parents=True, exist_ok=False)

        (run_dir / "result.json").write_text(
            result.model_dump_json(indent=2),
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


def load_result(path: Path | str) -> RunResult:
    return RunResult.model_validate_json(Path(path).read_text(encoding="utf-8"))
