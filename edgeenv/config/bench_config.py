from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class BenchmarkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    command: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    model_format: str = Field(min_length=1)
    model_path: str = Field(min_length=1)
    task: str = Field(min_length=1)
    input_shape: list[int] = Field(min_length=1)
    input_dtype: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    execution_provider: str = Field(min_length=1)
    precision: str = Field(min_length=1)
    batch_size: int = Field(gt=0)
    warmup_runs: int = Field(ge=0)
    repeat_runs: int = Field(gt=0)
    include_preprocess: bool
    include_postprocess: bool

    @field_validator("input_shape")
    @classmethod
    def validate_input_shape(cls, value: list[int]) -> list[int]:
        if any(dim <= 0 for dim in value):
            raise ValueError("input_shape dimensions must be positive integers")
        return value


def load_benchmark_config(path: Path | str) -> BenchmarkConfig:
    source = Path(path)
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Benchmark config not found: {source}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in benchmark config {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Benchmark config must be a YAML mapping: {source}")

    try:
        return BenchmarkConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid benchmark config {source}: {exc}") from exc


BenchmarkRuntime = Literal["onnxruntime", "tensorrt", "fake"]
