from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from inferedge_env.registry.artifacts import default_registry_path
from inferedge_env.registry.models import RegistryRecord
from inferedge_env.result.schema import RunResult


class RunRegistry:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else default_registry_path()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    target TEXT NOT NULL,
                    model TEXT NOT NULL,
                    runtime TEXT NOT NULL,
                    protocol TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    result_path TEXT NOT NULL
                )
                """
            )

    def insert(self, result: RunResult, result_path: Path | str) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, target, model, runtime, protocol, metrics, result_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.created_at.isoformat(),
                    json.dumps(result.target.model_dump(), sort_keys=True),
                    json.dumps(result.model.model_dump(), sort_keys=True),
                    json.dumps(result.runtime.model_dump(), sort_keys=True),
                    json.dumps(result.protocol.model_dump(), sort_keys=True),
                    json.dumps(result.metrics.model_dump(), sort_keys=True),
                    str(result_path),
                ),
            )

    def list_runs(self) -> list[RegistryRecord]:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT run_id, created_at, target, model, runtime, protocol, metrics, result_path
                FROM runs
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [self._record_from_row(row) for row in rows]

    def show(self, run_id: str) -> RegistryRecord:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT run_id, created_at, target, model, runtime, protocol, metrics, result_path
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Run not found: {run_id}")
        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(row: Iterable[str]) -> RegistryRecord:
        (
            run_id,
            created_at,
            target,
            model,
            runtime,
            protocol,
            metrics,
            result_path,
        ) = row
        return RegistryRecord(
            run_id=run_id,
            created_at=created_at,
            target=json.loads(target),
            model=json.loads(model),
            runtime=json.loads(runtime),
            protocol=json.loads(protocol),
            metrics=json.loads(metrics),
            result_path=result_path,
        )
