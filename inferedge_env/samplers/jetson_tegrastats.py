from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.samplers.base import (
    SAMPLER_METADATA_SCHEMA_VERSION,
    SamplerContext,
    SamplerCorruptResourceMetrics,
    SamplerNoSamples,
    SamplerPermissionDenied,
    SamplerRawArtifactWriteFailed,
    SamplerStartFailedRequired,
    SamplerStopTimeout,
    SamplerSummary,
    SamplerUnavailable,
    SamplerUnparseableOutput,
)


SAMPLER_NAME = "jetson-tegrastats"
SAMPLER_VERSION = "0.1"
PLATFORM_TOOL = "tegrastats"
BENCHMARK_WINDOW = "sampler-start-before-command-stop-after-command"
SAMPLING_SCOPE = "host"


@dataclass(frozen=True)
class TegrastatsSample:
    raw_line: str
    memory_used_mb: float | None
    vdd_in_instant_w: float | None
    vdd_in_average_w: float | None
    temperature_peak_c: float | None


def parse_tegrastats_line(line: str) -> TegrastatsSample | None:
    memory_used = _parse_memory_mb(line)
    instant_mw, average_mw = _parse_vdd_in_mw(line)
    temperatures = _parse_temperatures_c(line)
    if memory_used is None and instant_mw is None and not temperatures:
        return None
    return TegrastatsSample(
        raw_line=line,
        memory_used_mb=memory_used,
        vdd_in_instant_w=instant_mw / 1000.0 if instant_mw is not None else None,
        vdd_in_average_w=average_mw / 1000.0 if average_mw is not None else None,
        temperature_peak_c=max(temperatures) if temperatures else None,
    )


def summarize_tegrastats_samples(
    lines: list[str],
    *,
    sampling_interval_ms: int | None = None,
    startup_wait_ms: int | None = None,
    platform_tool_path: str | None = None,
    raw_artifact: str | None = None,
    warnings: list[str] | None = None,
) -> tuple[ResourceMetrics, dict]:
    if not lines:
        raise SamplerNoSamples("tegrastats produced no samples")

    samples = [sample for line in lines if (sample := parse_tegrastats_line(line))]
    if not samples:
        raise SamplerUnparseableOutput("tegrastats output had no supported fields")

    memory_values = [
        sample.memory_used_mb for sample in samples if sample.memory_used_mb is not None
    ]
    instant_power_values = [
        sample.vdd_in_instant_w
        for sample in samples
        if sample.vdd_in_instant_w is not None
    ]
    average_power_values = [
        sample.vdd_in_average_w
        for sample in samples
        if sample.vdd_in_average_w is not None
    ]
    temperature_values = [
        sample.temperature_peak_c
        for sample in samples
        if sample.temperature_peak_c is not None
    ]

    payload: dict[str, float | str] = {"source": SAMPLER_NAME}
    if memory_values:
        payload["memory_mean_mb"] = _mean(memory_values)
        payload["memory_peak_mb"] = max(memory_values)
    if average_power_values or instant_power_values:
        payload["power_mean_w"] = _mean(average_power_values or instant_power_values)
    if instant_power_values:
        payload["power_peak_w"] = max(instant_power_values)
    if temperature_values:
        payload["temperature_peak_c"] = max(temperature_values)

    try:
        metrics = ResourceMetrics.model_validate(payload)
    except ValidationError as exc:
        raise SamplerCorruptResourceMetrics("Invalid tegrastats metrics") from exc

    metadata = _metadata(
        sample_count=len(samples),
        sampling_interval_ms=sampling_interval_ms,
        startup_wait_ms=startup_wait_ms,
        platform_tool_path=platform_tool_path,
        raw_artifacts=[raw_artifact] if raw_artifact else [],
        warnings=warnings or [],
    )
    return metrics, metadata


class JetsonTegrastatsSampler:
    name = SAMPLER_NAME

    def __init__(
        self,
        *,
        tegrastats_path: str = PLATFORM_TOOL,
        interval_ms: int = 500,
        startup_wait_ms: int = 250,
        required: bool = False,
        raw_log: bool = True,
        stop_timeout_seconds: float = 3.0,
    ) -> None:
        self.tegrastats_path = tegrastats_path
        self.interval_ms = interval_ms
        self.startup_wait_ms = startup_wait_ms
        self.required = required
        self.raw_log = raw_log
        self.stop_timeout_seconds = stop_timeout_seconds
        self._context: SamplerContext | None = None
        self._process: subprocess.Popen[str] | None = None
        self._resolved_path: str | None = None
        self._lines: list[str] = []
        self._warnings: list[str] = []
        self._raw_artifact: Path | None = None
        self._stopped = False

    def start(self, context: SamplerContext) -> None:
        self._context = context
        self._warnings = []
        self._lines = []
        self._raw_artifact = None
        self._stopped = False
        self._resolved_path = shutil.which(self.tegrastats_path) or self.tegrastats_path
        try:
            self._process = subprocess.Popen(
                [self._resolved_path, "--interval", str(self.interval_ms)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except PermissionError as exc:
            self._handle_start_error(
                SamplerPermissionDenied(
                    f"tegrastats permission denied: {self.tegrastats_path}"
                ),
                exc,
            )
        except OSError as exc:
            self._handle_start_error(
                SamplerUnavailable(f"tegrastats unavailable: {self.tegrastats_path}"),
                exc,
            )
        if self._process is not None and self.startup_wait_ms > 0:
            time.sleep(self.startup_wait_ms / 1000.0)

    def stop(self) -> None:
        self._stopped = True
        if self._process is None:
            return
        self._process.terminate()
        try:
            stdout, stderr = self._process.communicate(
                timeout=self.stop_timeout_seconds
            )
        except subprocess.TimeoutExpired:
            self._process.kill()
            stdout, stderr = self._process.communicate()
            self._warnings.append("tegrastats stop timed out; process was killed")
            if self.required:
                raise SamplerStopTimeout("tegrastats stop timed out")
        if stderr:
            self._warnings.append(stderr.strip())
        self._lines = stdout.splitlines()
        if self.raw_log and self._context is not None:
            self._raw_artifact = self._write_raw_log(self._context.artifact_dir)

    def summary(self) -> SamplerSummary:
        if self._context is None:
            return SamplerSummary(
                resource_metrics=None,
                metadata=self._empty_metadata(),
                warnings=["sampler was not started"],
            )
        if self._process is None:
            return SamplerSummary(
                resource_metrics=None,
                metadata=self._empty_metadata(),
                warnings=list(self._warnings),
            )
        if not self._stopped:
            self.stop()
        raw_artifact_rel = (
            _relative_raw_artifact(self._context.artifact_dir, self._raw_artifact)
            if self._raw_artifact is not None
            else None
        )
        try:
            metrics, metadata = summarize_tegrastats_samples(
                self._lines,
                sampling_interval_ms=self.interval_ms,
                startup_wait_ms=self.startup_wait_ms,
                platform_tool_path=self._resolved_path,
                raw_artifact=raw_artifact_rel,
                warnings=self._warnings,
            )
        except (SamplerNoSamples, SamplerUnparseableOutput) as exc:
            warnings = [*self._warnings, str(exc)]
            return SamplerSummary(
                resource_metrics=None,
                metadata=self._empty_metadata(warnings=warnings),
                raw_artifacts=self._raw_artifacts(),
                warnings=warnings,
            )
        return SamplerSummary(
            resource_metrics=metrics,
            metadata=metadata,
            raw_artifacts=self._raw_artifacts(),
            warnings=list(self._warnings),
        )

    def _handle_start_error(self, error: Exception, cause: Exception) -> None:
        if self.required:
            raise SamplerStartFailedRequired(str(error)) from cause
        self._warnings.append(str(error))
        self._process = None

    def _write_raw_log(self, artifact_dir: Path) -> Path:
        path = artifact_dir / "sampler" / "tegrastats.log"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "\n".join(self._lines) + ("\n" if self._lines else ""),
                encoding="utf-8",
            )
        except OSError as exc:
            if self.required:
                raise SamplerRawArtifactWriteFailed(
                    f"Failed to write tegrastats raw artifact: {path}"
                ) from exc
            self._warnings.append(f"Failed to write tegrastats raw artifact: {path}")
        return path

    def _empty_metadata(self, warnings: list[str] | None = None) -> dict:
        return _metadata(
            sample_count=0,
            sampling_interval_ms=self.interval_ms,
            startup_wait_ms=self.startup_wait_ms,
            platform_tool_path=self._resolved_path,
            raw_artifacts=[],
            warnings=warnings or self._warnings,
        )

    def _raw_artifacts(self) -> list[Path]:
        if self._raw_artifact is None:
            return []
        return [self._raw_artifact]


def _parse_memory_mb(line: str) -> float | None:
    match = re.search(r"\bRAM\s+(\d+(?:\.\d+)?)/\d+(?:\.\d+)?MB\b", line)
    if match is None:
        return None
    return float(match.group(1))


def _parse_vdd_in_mw(line: str) -> tuple[float | None, float | None]:
    match = re.search(
        r"\bVDD_IN\s+(\d+(?:\.\d+)?)mW(?:/(\d+(?:\.\d+)?)mW)?\b",
        line,
    )
    if match is None:
        return None, None
    instant = float(match.group(1))
    average = float(match.group(2)) if match.group(2) is not None else None
    return instant, average


def _parse_temperatures_c(line: str) -> list[float]:
    return [
        float(value)
        for value in re.findall(r"\b[a-zA-Z0-9_]+@(\d+(?:\.\d+)?)C\b", line)
    ]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _metadata(
    *,
    sample_count: int,
    sampling_interval_ms: int | None,
    startup_wait_ms: int | None,
    platform_tool_path: str | None,
    raw_artifacts: list[str],
    warnings: list[str],
) -> dict:
    return {
        "schema_version": SAMPLER_METADATA_SCHEMA_VERSION,
        "sampler_name": SAMPLER_NAME,
        "sampler_version": SAMPLER_VERSION,
        "platform_tool": PLATFORM_TOOL,
        "platform_tool_path": platform_tool_path,
        "platform_tool_version": None,
        "sampling_interval_ms": sampling_interval_ms,
        "startup_wait_ms": startup_wait_ms,
        "sampling_scope": SAMPLING_SCOPE,
        "benchmark_window": BENCHMARK_WINDOW,
        "sample_count": sample_count,
        "raw_artifacts": raw_artifacts,
        "fields": {
            "memory_mean_mb": {
                "source_field": "RAM used",
                "unit": "MB",
                "aggregation": "mean",
            },
            "memory_peak_mb": {
                "source_field": "RAM used",
                "unit": "MB",
                "aggregation": "max",
            },
            "power_mean_w": {
                "source_field": "VDD_IN average",
                "unit": "W",
                "aggregation": "mean",
            },
            "power_peak_w": {
                "source_field": "VDD_IN instant",
                "unit": "W",
                "aggregation": "max",
            },
            "temperature_peak_c": {
                "source_field": "*@...C",
                "unit": "C",
                "aggregation": "max",
            },
        },
        "warnings": warnings,
    }


def _relative_raw_artifact(artifact_dir: Path, raw_artifact: Path | None) -> str | None:
    if raw_artifact is None:
        return None
    try:
        return raw_artifact.relative_to(artifact_dir).as_posix()
    except ValueError:
        return raw_artifact.as_posix()
