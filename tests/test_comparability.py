from __future__ import annotations

from inferedge_env.compare.comparability import check_comparability
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.runners.fake import FakeRunner
from helpers import make_result


def test_comparability_same_condition(bench_config, target_profile):
    left = make_result(bench_config, target_profile, run_id="run-a")
    right = make_result(bench_config, target_profile, run_id="run-b")

    report = check_comparability(left, right)

    assert report.comparable == "Yes"
    assert report.mode == "same-condition"
    assert "Same benchmark protocol" in report.reasons


def test_comparability_no_for_different_model_hash(bench_config, target_profile):
    left = make_result(bench_config, target_profile, run_id="run-a")
    changed = bench_config.model_copy(update={"model_path": "models/other.onnx"})
    right = make_result(changed, target_profile, run_id="run-b")

    report = check_comparability(left, right)

    assert report.comparable == "No"
    assert report.mode is None
    assert "Different model hash" in report.reasons


def test_comparability_conditional_for_runtime_difference(bench_config, target_profile):
    left = make_result(bench_config, target_profile, run_id="run-a")
    changed = bench_config.model_copy(update={"runtime": "other-runtime"})
    right = make_result(changed, target_profile, run_id="run-b")

    report = check_comparability(left, right)

    assert report.comparable == "Conditional"
    assert report.mode == "runtime-comparison"
    assert "Different runtime or execution provider" in report.reasons


def test_comparability_ignores_resource_metrics_presence(bench_config, target_profile):
    left = make_result(bench_config, target_profile, run_id="run-a")
    runner_result = FakeRunner().run(bench_config, target_profile).model_copy(
        update={"resource_metrics": ResourceMetrics(memory_peak_mb=512.0)}
    )
    right = make_result(
        bench_config,
        target_profile,
        run_id="run-b",
        runner_result=runner_result,
    )

    report = check_comparability(left, right)

    assert report.comparable == "Yes"
    assert report.mode == "same-condition"


def test_comparability_ignores_runtime_operation_summary_presence(
    bench_config,
    target_profile,
):
    left = make_result(bench_config, target_profile, run_id="run-a")
    runner_result = FakeRunner().run(bench_config, target_profile).model_copy(
        update={
            "runtime_operation_summary": {
                "source": "inferedge-runtime",
                "health_reason": "completed",
            }
        }
    )
    right = make_result(
        bench_config,
        target_profile,
        run_id="run-b",
        runner_result=runner_result,
    )

    report = check_comparability(left, right)

    assert report.comparable == "Yes"
    assert report.mode == "same-condition"
