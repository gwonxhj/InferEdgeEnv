from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_shape: list[int]
    input_dtype: str
    task: str
    precision: str
    batch_size: int
    warmup_runs: int
    repeat_runs: int
    include_preprocess: bool
    include_postprocess: bool


class ModelIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    model_version: str
    model_format: str
    model_path: str
    model_hash: str


class RuntimeIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime: str
    execution_provider: str


class TargetIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_name: str
    target_type: str
    board_name: str
    os: str
    runtime_tags: list[str]


class BenchmarkMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    throughput_fps: float


class ResourceMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_peak_mb: float | None = None
    memory_mean_mb: float | None = None
    power_mean_w: float | None = None
    power_peak_w: float | None = None
    energy_j: float | None = None
    temperature_peak_c: float | None = None
    source: str | None = None


class RunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "edgeenv.result.v1"
    run_id: str
    created_at: datetime
    benchmark_name: str
    command: str
    model: ModelIdentity
    runtime: RuntimeIdentity
    target: TargetIdentity
    protocol: BenchmarkProtocol
    metrics: BenchmarkMetrics
    resource_metrics: ResourceMetrics | None = None
    env: dict[str, Any] = Field(default_factory=dict)

    @property
    def model_hash(self) -> str:
        return self.model.model_hash
