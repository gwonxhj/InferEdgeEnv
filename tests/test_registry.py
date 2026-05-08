from __future__ import annotations

import sqlite3

from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.result.writer import ResultArtifactWriter
from helpers import make_result


def test_registry_insert_list_show(tmp_path, bench_config, target_profile):
    registry = RunRegistry(tmp_path / ".edgeenv" / "runs.db")
    result = make_result(bench_config, target_profile, run_id="run-registry")
    result_path = tmp_path / ".edgeenv" / "runs" / "run-registry" / "result.json"

    registry.insert(result, result_path)

    records = registry.list_runs()
    shown = registry.show("run-registry")

    assert [record.run_id for record in records] == ["run-registry"]
    assert shown.model["model_name"] == "yolov8n-fire"
    assert shown.runtime["runtime"] == "fake-runtime"
    assert shown.metrics["latency_mean_ms"] == 12.588
    assert shown.result_path == str(result_path)


def test_registry_indexes_resource_metrics(tmp_path, bench_config, target_profile):
    registry = RunRegistry(tmp_path / ".edgeenv" / "runs.db")
    result = make_result(bench_config, target_profile, run_id="run-resource")
    result = result.model_copy(
        update={
            "resource_metrics": ResourceMetrics(
                memory_peak_mb=512.0,
                power_mean_w=8.2,
                source="benchmark-command",
            )
        }
    )
    result_path = tmp_path / ".edgeenv" / "runs" / "run-resource" / "result.json"

    registry.insert(result, result_path)

    records = registry.list_resource_metrics(metric_name="memory_peak_mb")

    assert len(records) == 1
    assert records[0].run_id == "run-resource"
    assert records[0].metric_name == "memory_peak_mb"
    assert records[0].metric_value == 512.0
    assert records[0].unit == "mb"
    assert records[0].source == "benchmark-command"


def test_registry_resource_metric_filters(tmp_path, bench_config, target_profile):
    registry = RunRegistry(tmp_path / ".edgeenv" / "runs.db")
    first = make_result(bench_config, target_profile, run_id="run-low").model_copy(
        update={
            "resource_metrics": ResourceMetrics(
                memory_peak_mb=128.0,
                source="sampler-a",
            )
        }
    )
    second = make_result(bench_config, target_profile, run_id="run-high").model_copy(
        update={
            "resource_metrics": ResourceMetrics(
                memory_peak_mb=512.0,
                source="sampler-b",
            )
        }
    )

    registry.insert(first, tmp_path / ".edgeenv" / "runs" / "run-low" / "result.json")
    registry.insert(second, tmp_path / ".edgeenv" / "runs" / "run-high" / "result.json")

    records = registry.list_resource_metrics(
        metric_name="memory_peak_mb",
        min_value=500.0,
        source="sampler-b",
    )

    assert [record.run_id for record in records] == ["run-high"]


def test_registry_backfills_resource_index_from_existing_result_artifacts(
    tmp_path,
    bench_config,
    target_profile,
):
    edgeenv_root = tmp_path / ".edgeenv"
    db_path = edgeenv_root / "runs.db"
    result = make_result(bench_config, target_profile, run_id="run-backfill")
    result = result.model_copy(
        update={
            "resource_metrics": ResourceMetrics(
                power_peak_w=9.5,
                source="imported-artifact",
            )
        }
    )
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result=result,
        config_path="examples/benches/yolov8n_fire.yaml",
        target_path="examples/profiles/local_fake.yaml",
        stdout="",
        stderr="",
    )
    result_path = run_dir / "result.json"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE runs (
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
            INSERT INTO runs (
                run_id, created_at, target, model, runtime, protocol, metrics, result_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.run_id,
                result.created_at.isoformat(),
                result.target.model_dump_json(),
                result.model.model_dump_json(),
                result.runtime.model_dump_json(),
                result.protocol.model_dump_json(),
                result.metrics.model_dump_json(),
                str(result_path),
            ),
        )

    records = RunRegistry(db_path).list_resource_metrics(metric_name="power_peak_w")

    assert len(records) == 1
    assert records[0].run_id == "run-backfill"
    assert records[0].metric_value == 9.5
    assert records[0].unit == "w"
