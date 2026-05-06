from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.result.schema import ResourceMetrics


class RunnerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_fps: float
    resource_metrics: ResourceMetrics | None = None
    stdout: str
    stderr: str


class BenchmarkRunner(Protocol):
    def run(self, config: BenchmarkConfig, target: TargetProfile) -> RunnerResult:
        """Run a benchmark and return measured metrics."""
