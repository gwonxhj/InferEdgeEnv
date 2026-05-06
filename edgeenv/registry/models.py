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
