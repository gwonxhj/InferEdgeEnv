from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


TargetType = Literal["fake", "local"]
SamplerName = Literal["jetson-tegrastats"]


class SamplerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: SamplerName
    required: bool = False
    interval_ms: int = Field(default=500, gt=0)
    startup_wait_ms: int = Field(default=600, ge=0)
    raw_log: bool = True
    tegrastats_path: str = Field(default="tegrastats", min_length=1)


class TargetProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_name: str = Field(min_length=1)
    target_type: TargetType
    board_name: str = Field(min_length=1)
    os: str = Field(min_length=1)
    runtime_tags: list[str] = Field(default_factory=list)
    sampler: SamplerProfile | None = None


def load_target_profile(path: Path | str) -> TargetProfile:
    source = Path(path)
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Target profile not found: {source}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in target profile {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Target profile must be a YAML mapping: {source}")

    try:
        return TargetProfile.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid target profile {source}: {exc}") from exc
