from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RegistryRecord(BaseModel):
    run_id: str
    created_at: datetime
    target: dict
    model: dict
    runtime: dict
    protocol: dict
    metrics: dict
    result_path: str


class ResourceMetricRecord(BaseModel):
    run_id: str
    created_at: datetime
    target_name: str
    model_name: str
    metric_name: str
    metric_value: float
    unit: str
    source: str | None = None
