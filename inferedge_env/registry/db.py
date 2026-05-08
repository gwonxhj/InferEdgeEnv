from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from inferedge_env.registry.artifacts import default_registry_path
from inferedge_env.registry.models import RegistryRecord, ResourceMetricRecord
from inferedge_env.result.schema import RunResult
from inferedge_env.result.writer import load_result


RESOURCE_METRIC_UNITS = {
    "memory_peak_mb": "mb",
    "memory_mean_mb": "mb",
    "power_mean_w": "w",
    "power_peak_w": "w",
    "energy_j": "j",
    "temperature_peak_c": "c",
}


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resource_metric_index (
                    run_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    unit TEXT NOT NULL,
                    source TEXT,
                    PRIMARY KEY (run_id, metric_name),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_resource_metric_lookup
                ON resource_metric_index (metric_name, metric_value)
                """
            )
            self._backfill_resource_metric_index(conn)

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
            self._replace_resource_metric_index(conn, result)

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

    def list_resource_metrics(
        self,
        *,
        metric_name: str | None = None,
        source: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> list[ResourceMetricRecord]:
        self.initialize()
        if metric_name is not None and metric_name not in RESOURCE_METRIC_UNITS:
            valid = ", ".join(sorted(RESOURCE_METRIC_UNITS))
            raise ValueError(f"Unsupported resource metric: {metric_name}. Valid: {valid}")

        conditions: list[str] = []
        params: list[object] = []
        if metric_name is not None:
            conditions.append("rmi.metric_name = ?")
            params.append(metric_name)
        if source is not None:
            conditions.append("rmi.source = ?")
            params.append(source)
        if min_value is not None:
            conditions.append("rmi.metric_value >= ?")
            params.append(min_value)
        if max_value is not None:
            conditions.append("rmi.metric_value <= ?")
            params.append(max_value)

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT
                    runs.run_id,
                    runs.created_at,
                    runs.target,
                    runs.model,
                    rmi.metric_name,
                    rmi.metric_value,
                    rmi.unit,
                    rmi.source
                FROM resource_metric_index AS rmi
                JOIN runs ON runs.run_id = rmi.run_id
                {where}
                ORDER BY runs.created_at DESC, rmi.metric_name ASC
                """,
                params,
            ).fetchall()
        return [self._resource_metric_record_from_row(row) for row in rows]

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

    @staticmethod
    def _resource_metric_record_from_row(row: Iterable[object]) -> ResourceMetricRecord:
        (
            run_id,
            created_at,
            target,
            model,
            metric_name,
            metric_value,
            unit,
            source,
        ) = row
        target_payload = json.loads(str(target))
        model_payload = json.loads(str(model))
        return ResourceMetricRecord(
            run_id=str(run_id),
            created_at=str(created_at),
            target_name=target_payload["target_name"],
            model_name=model_payload["model_name"],
            metric_name=str(metric_name),
            metric_value=float(metric_value),
            unit=str(unit),
            source=str(source) if source is not None else None,
        )

    @staticmethod
    def _replace_resource_metric_index(
        conn: sqlite3.Connection,
        result: RunResult,
    ) -> None:
        conn.execute(
            "DELETE FROM resource_metric_index WHERE run_id = ?",
            (result.run_id,),
        )
        if result.resource_metrics is None:
            return
        payload = result.resource_metrics.model_dump(mode="json", exclude_none=True)
        source = payload.get("source")
        for metric_name, unit in RESOURCE_METRIC_UNITS.items():
            value = payload.get(metric_name)
            if value is None:
                continue
            conn.execute(
                """
                INSERT OR REPLACE INTO resource_metric_index (
                    run_id, metric_name, metric_value, unit, source
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (result.run_id, metric_name, float(value), unit, source),
            )

    def _backfill_resource_metric_index(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute(
            """
            SELECT run_id, result_path
            FROM runs
            WHERE run_id NOT IN (
                SELECT DISTINCT run_id FROM resource_metric_index
            )
            """
        ).fetchall()
        for _run_id, result_path in rows:
            try:
                result = load_result(str(result_path))
            except (OSError, ValueError):
                continue
            self._replace_resource_metric_index(conn, result)
