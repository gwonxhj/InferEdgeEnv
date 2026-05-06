from __future__ import annotations

from edgeenv.compare.comparability import check_comparability
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
