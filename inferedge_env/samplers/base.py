from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from inferedge_env.result.schema import ResourceMetrics


SAMPLER_METADATA_SCHEMA_VERSION = "edgeenv.sampler-metadata.v1"


@dataclass(frozen=True)
class SamplerContext:
    run_id: str
    benchmark_name: str
    target_name: str
    target_type: str
    command: list[str]
    artifact_dir: Path
    monotonic_start_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SamplerSummary:
    resource_metrics: ResourceMetrics | None
    metadata: dict[str, Any]
    raw_artifacts: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Sampler(Protocol):
    name: str

    def start(self, context: SamplerContext) -> None:
        ...

    def stop(self) -> None:
        ...

    def summary(self) -> SamplerSummary:
        ...


class SamplerError(RuntimeError):
    """Base class for sampler adapter errors."""


class RecoverableSamplerError(SamplerError):
    """Sampler failed without invalidating the primary benchmark result."""


class FatalSamplerError(SamplerError):
    """Sampler failure should fail the run when sampler output is required."""


class SamplerUnavailable(RecoverableSamplerError):
    """Platform sampler tool is missing or cannot be started."""


class SamplerPermissionDenied(RecoverableSamplerError):
    """Platform sampler tool exists but cannot run with current permissions."""


class SamplerNoSamples(RecoverableSamplerError):
    """Sampler started but produced no samples."""


class SamplerUnparseableOutput(RecoverableSamplerError):
    """Sampler output did not contain supported resource fields."""


class SamplerStopTimeout(RecoverableSamplerError):
    """Sampler did not stop cleanly and required force cleanup."""


class SamplerStartFailedRequired(FatalSamplerError):
    """Required sampler could not start."""


class SamplerCorruptResourceMetrics(FatalSamplerError):
    """Sampler generated invalid normalized resource metrics."""


class SamplerRawArtifactWriteFailed(FatalSamplerError):
    """Sampler raw artifact could not be persisted when required."""
