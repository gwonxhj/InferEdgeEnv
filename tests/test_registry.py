from __future__ import annotations

from inferedge_env.registry.db import RunRegistry
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
