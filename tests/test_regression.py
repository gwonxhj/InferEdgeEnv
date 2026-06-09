from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from inferedge_env.cli import app
from inferedge_env.compare.regression import (
    analyze_regression,
    render_regression_markdown,
)
from inferedge_env.config.bench_config import BenchmarkConfig
from inferedge_env.config.target_profile import TargetProfile
from inferedge_env.registry.db import RunRegistry
from inferedge_env.result.schema import ResourceMetrics
from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES,
    ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
    ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
    ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
    ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
    ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS,
    ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
)
from inferedge_env.result.writer import ResultArtifactWriter
from inferedge_env.runners.base import RunnerResult
from helpers import make_result


EXAMPLE_REGRESSION_DIR = Path("examples/regression")


def test_regression_detects_same_condition_latency_and_resource_regression(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            memory_peak_mb=100.0,
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=118.0,
            p95=132.0,
            p99=171.6,
            fps=39.0,
            memory_peak_mb=140.0,
        ),
    )

    report = analyze_regression(baseline, candidate)

    assert report.comparable is True
    assert report.mode == "same-condition"
    assert report.regression_detected is True
    assert report.regression_type == "mixed"
    assert report.severity == "high"
    assert report.recommendation == "review_required"
    assert report.evidence["mean_delta_pct"] == 18.0
    assert report.evidence["p99_delta_pct"] == 32.0
    assert report.evidence["fps_delta_pct"] == -22.0
    assert report.evidence["memory_peak_delta_pct"] == 40.0
    triggered = {item["name"] for item in report.evidence["triggered_thresholds"]}
    assert "mean_latency_review" in triggered
    assert "p99_latency_high" in triggered
    assert "fps_drop_review" in triggered
    assert "memory_peak_warning" in triggered


def test_regression_attaches_runtime_telemetry_history_context(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=112.0,
            p95=125.0,
            p99=135.0,
            fps=48.0,
            runtime_telemetry=_runtime_telemetry(
                sequence_id=2,
                missing_fields=["queue_depth"],
            ),
        ),
    )
    telemetry_history = {
        "schema_version": "edgeenv.runtime-telemetry-history.v1",
        "summary": {
            "registered_runs": 2,
            "telemetry_runs": 2,
            "missing_telemetry_runs": 0,
        },
        "telemetry_coverage": {
            "runs_with_coverage": 1,
            "runs_without_coverage": 1,
            "expected_fields": [
                "gpu_temperature",
                "queue_depth",
                "telemetry_timestamp",
            ],
            "observed_fields": ["gpu_temperature", "telemetry_timestamp"],
            "missing_fields": ["queue_depth"],
            "coverage_ratio_min": 0.666667,
            "coverage_ratio_max": 0.666667,
            "missing_telemetry_is_failure_values": [False],
            "any_missing_telemetry_is_failure": False,
            "missing_field_run_count": 1,
            "missing_field_runs": [
                {
                    "run_id": "candidate",
                    "missing_fields": ["queue_depth"],
                    "missing_field_count": 1,
                    "missing_telemetry_is_failure": False,
                }
            ],
        },
        "runs": [
            {
                "run_id": "baseline",
                "telemetry_timestamp": "2026-05-22T00:00:01Z",
                "execution_sequence_id": 1,
            },
            {
                "run_id": "candidate",
                "telemetry_timestamp": "2026-05-22T00:00:02Z",
                "execution_sequence_id": 2,
                "runtime_telemetry": candidate.runtime_telemetry,
            },
        ],
        "missing_telemetry": [],
    }

    report = analyze_regression(
        baseline,
        candidate,
        telemetry_history=telemetry_history,
    )

    payload = report.to_dict()
    context = payload["runtime_telemetry_context"]
    assert context["source"] == "result_artifacts+runtime_telemetry_history"
    assert context["history"]["schema_version"] == (
        "edgeenv.runtime-telemetry-history.v1"
    )
    assert context["history"]["telemetry_coverage"]["missing_field_runs"] == [
        {
            "run_id": "candidate",
            "missing_fields": ["queue_depth"],
            "missing_field_count": 1,
            "missing_telemetry_is_failure": False,
        }
    ]
    assert context["baseline"]["result_telemetry_present"] is True
    assert context["baseline"]["history_entry_present"] is True
    assert context["candidate"]["execution_sequence_id"] == 2
    assert context["candidate"]["telemetry_coverage"] == {
        "schema_version": "inferedge-runtime-telemetry-coverage-v1",
        "expected_fields": [
            "gpu_temperature",
            "queue_depth",
            "telemetry_timestamp",
        ],
        "observed_fields": ["gpu_temperature", "telemetry_timestamp"],
        "missing_fields": ["queue_depth"],
        "expected_field_count": 3,
        "observed_field_count": 2,
        "missing_field_count": 1,
        "coverage_ratio": 0.666667,
        "comparability_owner": "edgeenv",
        "missing_telemetry_is_failure": False,
    }
    assert context["candidate"]["history_telemetry_coverage"]["missing_fields"] == [
        "queue_depth"
    ]
    assert context["evidence_gaps"] == []
    assert report.evidence["mean_delta_pct"] == 12.0


def test_regression_preserves_history_seed_run_config_replay_context(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=118.0,
            p95=132.0,
            p99=171.6,
            fps=39.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=2),
        ),
    )
    telemetry_history = {
        "schema_version": "edgeenv.runtime-telemetry-history.v1",
        "summary": {
            "registered_runs": 2,
            "telemetry_runs": 2,
            "history_seed_runs": 2,
            "history_seed_run_config_runs": 2,
            "missing_telemetry_runs": 0,
        },
        "runs": [
            {
                "run_id": "baseline",
                "telemetry_timestamp": "2026-05-22T00:00:01Z",
                "execution_sequence_id": 1,
                "runtime_telemetry_history_seed": _runtime_history_seed(
                    "baseline",
                    sequence_id=1,
                ),
            },
            {
                "run_id": "candidate",
                "telemetry_timestamp": "2026-05-22T00:00:02Z",
                "execution_sequence_id": 2,
                "runtime_telemetry_history_seed": _runtime_history_seed(
                    "candidate",
                    sequence_id=2,
                ),
            },
        ],
        "missing_telemetry": [],
    }

    report = analyze_regression(
        baseline,
        candidate,
        telemetry_history=telemetry_history,
    )

    context = report.to_dict()["runtime_telemetry_context"]
    assert context["history"]["summary"]["history_seed_runs"] == 2
    assert context["history"]["summary"]["history_seed_run_config_runs"] == 2
    assert context["history"]["runs"][0]["runtime_telemetry_history_seed"][
        "registry_owner"
    ] == "edgeenv"
    assert context["baseline"]["runtime_telemetry_history_seed_present"] is True
    assert context["baseline"]["history_seed_registry_owner"] == "edgeenv"
    assert context["baseline"]["history_seed_decision_owner"] == "lab"
    assert context["baseline"]["history_seed_run_config"] == {
        "batch": 1,
        "height": 224,
        "width": 224,
        "warmup": 10,
        "runs": 100,
        "timeout_ms": None,
        "input_mode": "dummy",
        "input_preprocess": "none",
        "power_mode": "unknown",
        "jetson_clocks": "unknown",
    }
    assert context["candidate"]["history_seed_run_config"]["runs"] == 100
    assert report.mode == "same-condition"
    assert report.regression_detected is True


def test_regression_attaches_orchestrator_feed_as_supplemental_context(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=112.0,
            p95=125.0,
            p99=135.0,
            fps=48.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=2),
        ),
    )
    telemetry_history = {
        "schema_version": "edgeenv.runtime-telemetry-history.v1",
        "summary": {
            "registered_runs": 2,
            "telemetry_runs": 2,
            "missing_telemetry_runs": 0,
            "orchestrator_feed_runs": 1,
        },
        "runs": [
            {
                "run_id": "baseline",
                "telemetry_timestamp": "2026-05-22T00:00:01Z",
                "execution_sequence_id": 1,
            },
            {
                "run_id": "candidate",
                "telemetry_timestamp": "2026-05-22T00:00:02Z",
                "execution_sequence_id": 2,
                "orchestrator_operation_context": _orchestrator_context(
                    "candidate"
                ),
            },
        ],
        "missing_telemetry": [],
    }

    report = analyze_regression(
        baseline,
        candidate,
        telemetry_history=telemetry_history,
    )

    context = report.to_dict()["runtime_telemetry_context"]
    candidate_context = context["candidate"]
    assert report.mode == "same-condition"
    assert report.evidence["mean_delta_pct"] == 12.0
    assert candidate_context["orchestrator_context_present"] is True
    assert candidate_context["orchestrator_operation_context"][
        "not_a_regression_judgement"
    ] is True
    assert candidate_context["orchestrator_operation_context"][
        "source_repository"
    ] == ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY
    assert candidate_context["orchestrator_operation_context"]["artifact_role"] == (
        ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE
    )
    assert candidate_context["orchestrator_operation_context"][
        "producer_contract"
    ] == ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT
    assert candidate_context["orchestrator_operation_context"]["edgeenv_mapping_hint"][
        "coverage_summary_owner"
    ] == ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER
    assert candidate_context["orchestrator_operation_context"]["edgeenv_mapping_hint"][
        "coverage_summary_path"
    ] == ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH
    assert candidate_context["orchestrator_operation_context"]["edgeenv_mapping_hint"][
        "operation_context_role"
    ] == ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE
    assert candidate_context["orchestrator_operation_context"]["edgeenv_mapping_hint"][
        "candidate_context_required_fields"
    ] == [*ORCHESTRATOR_EDGEENV_REQUIRED_CANDIDATE_FIELDS]
    assert candidate_context["orchestrator_operation_context"]["edgeenv_mapping_hint"][
        "aiguard_evidence_candidates"
    ] == [*ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES]
    assert candidate_context["orchestrator_operation_context"]["candidate_context"][
        "operation"
    ]["queue_depth"] == 7
    assert candidate_context["orchestrator_operation_context"]["candidate_context"][
        "telemetry_source"
    ] == "inferedge_orchestrator_operation_summary"
    assert (
        "Orchestrator operation context is supplemental evidence, not a regression judgement."
        in context["notes"]
    )
    markdown = render_regression_markdown(report)
    assert "### Operation Context Quick Scan" in markdown
    assert (
        "| candidate | operation_summary: mode=n/a, max_queue=7, "
        "queue_pressure=n/a, deadline_missed=2, fallback=1, dropped=n/a |"
    ) in markdown


def test_regression_preserves_replay_sequence_order_mismatch_context(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=5),
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(
            mean=112.0,
            p95=125.0,
            p99=135.0,
            fps=48.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=2),
        ),
    )
    telemetry_history = {
        "schema_version": "edgeenv.runtime-telemetry-history.v1",
        "summary": {
            "registered_runs": 2,
            "telemetry_runs": 2,
            "missing_telemetry_runs": 0,
        },
        "runs": [
            {
                "run_id": "candidate",
                "telemetry_timestamp": "2026-05-22T00:00:02Z",
                "execution_sequence_id": 2,
            },
            {
                "run_id": "baseline",
                "telemetry_timestamp": "2026-05-22T00:00:05Z",
                "execution_sequence_id": 5,
            },
        ],
        "missing_telemetry": [],
    }

    report = analyze_regression(
        baseline,
        candidate,
        telemetry_history=telemetry_history,
    )

    context = report.to_dict()["runtime_telemetry_context"]
    assert report.comparable is True
    assert report.mode == "same-condition"
    assert context["baseline"]["execution_sequence_id"] == 5
    assert context["baseline"]["history_execution_sequence_id"] == 5
    assert context["candidate"]["execution_sequence_id"] == 2
    assert context["candidate"]["history_execution_sequence_id"] == 2
    assert context["evidence_gaps"] == []


def test_regression_records_runtime_telemetry_evidence_gap(
    bench_config,
    target_profile,
):
    baseline = make_result(
        bench_config,
        target_profile,
        run_id="baseline",
        runner_result=_runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    candidate = make_result(
        bench_config,
        target_profile,
        run_id="candidate",
        runner_result=_runner_result(mean=112.0, p95=125.0, p99=135.0, fps=48.0),
    )

    report = analyze_regression(baseline, candidate)

    assert report.runtime_telemetry_context is not None
    assert report.runtime_telemetry_context["evidence_gaps"] == [
        {
            "run_id": "candidate",
            "reason": "runtime_telemetry_missing_in_result",
        }
    ]


def test_regression_suppresses_delta_for_protocol_mismatch(
    bench_config,
    target_profile,
):
    baseline = make_result(bench_config, target_profile, run_id="baseline")
    changed = bench_config.model_copy(update={"repeat_runs": 30})
    candidate = make_result(changed, target_profile, run_id="candidate")

    report = analyze_regression(baseline, candidate)

    assert report.comparable is False
    assert report.mode == "protocol_mismatch"
    assert report.regression_detected is False
    assert report.regression_type == "not_evaluated"
    assert report.recommendation == "rerun_with_matching_protocol"
    assert "Different repeat runs" in report.evidence["comparability_reasons"]
    assert report.runtime_telemetry_context is None


def test_regression_cli_writes_json_and_markdown_reports(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(mean=100.0, p95=120.0, p99=130.0, fps=50.0),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "candidate",
        _runner_result(mean=118.0, p95=132.0, p99=171.6, fps=39.0),
    )
    json_path = tmp_path / "regression.json"
    md_path = tmp_path / "regression.md"

    result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "EdgeEnv Runtime Regression Report" in result.output
    assert "Comparable: true" in result.output
    assert "Mode: same-condition" in result.output
    assert "Regression detected: true" in result.output
    assert "Severity: high" in result.output
    assert "- mean_delta_pct: +18.0%" in result.output
    assert "p99_latency_high" in result.output
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["regression_detected"] is True
    assert payload["mode"] == "same-condition"
    assert payload["evidence"]["p99_delta_pct"] == 32.0
    markdown = md_path.read_text(encoding="utf-8")
    assert "# EdgeEnv Runtime Regression Report" in markdown
    assert "`review_required`" in markdown


def test_regression_cli_attaches_runtime_telemetry_history_context(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "candidate",
        _runner_result(
            mean=118.0,
            p95=132.0,
            p99=171.6,
            fps=39.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=2),
        ),
    )
    history_path = tmp_path / "runtime-telemetry-history.json"
    history_path.write_text(
        json.dumps(
            {
                "schema_version": "edgeenv.runtime-telemetry-history.v1",
                "summary": {
                    "registered_runs": 2,
                    "telemetry_runs": 2,
                    "missing_telemetry_runs": 0,
                },
                "runs": [
                    {"run_id": "baseline", "execution_sequence_id": 1},
                    {"run_id": "candidate", "execution_sequence_id": 2},
                ],
                "missing_telemetry": [],
            }
        ),
        encoding="utf-8",
    )
    json_path = tmp_path / "regression.json"
    md_path = tmp_path / "regression.md"

    result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
            "--telemetry-history",
            str(history_path),
            "--output-json",
            str(json_path),
            "--output-md",
            str(md_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Runtime Telemetry Context:" in result.output
    assert "- baseline: present=true, history=true" in result.output
    assert "- candidate: present=true, history=true" in result.output
    assert "- evidence_gaps: none" in result.output
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["runtime_telemetry_context"]["candidate"][
        "history_entry_present"
    ] is True
    markdown = md_path.read_text(encoding="utf-8")
    assert "## Runtime Telemetry Context" in markdown
    assert "edgeenv.runtime-telemetry-history.v1" in markdown


def test_cli_telemetry_replay_to_regression_smoke(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "candidate",
        _runner_result(
            mean=118.0,
            p95=132.0,
            p99=171.6,
            fps=39.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=2),
        ),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "telemetry-gap",
        _runner_result(mean=99.0, p95=110.0, p99=120.0, fps=52.0),
    )
    history_path = tmp_path / "runtime-telemetry-history.json"
    regression_json = tmp_path / "edgeenv-regression.json"
    regression_md = tmp_path / "edgeenv-regression.md"

    export_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "export-history",
            "--edgeenv-root",
            str(edgeenv_root),
            "--output",
            str(history_path),
        ],
    )
    inspect_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "inspect-history",
            str(history_path),
        ],
    )
    regression_result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
            "--telemetry-history",
            str(history_path),
            "--output-json",
            str(regression_json),
            "--output-md",
            str(regression_md),
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    assert "Telemetry entries: 2" in export_result.output
    assert "Missing telemetry: 1" in export_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Runtime telemetry history valid" in inspect_result.output
    assert "Replay runs: 2" in inspect_result.output
    assert "Evidence gaps: 1" in inspect_result.output
    assert "Scope: read-only local replay validation" in inspect_result.output
    assert regression_result.exit_code == 0, regression_result.output
    assert "Runtime Telemetry Context:" in regression_result.output
    assert "Regression detected: true" in regression_result.output
    assert "p99_latency_high" in regression_result.output

    history_payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert history_payload["summary"]["telemetry_runs"] == 2
    assert history_payload["summary"]["missing_telemetry_runs"] == 1
    regression_payload = json.loads(regression_json.read_text(encoding="utf-8"))
    context = regression_payload["runtime_telemetry_context"]
    assert context["role"] == "supplemental_runtime_telemetry_context"
    assert context["source"] == "result_artifacts+runtime_telemetry_history"
    assert context["history"]["summary"]["missing_telemetry_runs"] == 1
    assert context["history"]["summary"]["registered_runs"] == 3
    assert context["history"]["summary"]["telemetry_runs"] == 2
    assert context["baseline"]["run_id"] == "baseline"
    assert context["baseline"]["history_entry_present"] is True
    assert context["baseline"]["execution_sequence_id"] == 1
    assert context["baseline"]["history_execution_sequence_id"] == 1
    assert context["candidate"]["run_id"] == "candidate"
    assert context["candidate"]["history_entry_present"] is True
    assert context["candidate"]["execution_sequence_id"] == 2
    assert context["candidate"]["history_execution_sequence_id"] == 2
    assert context["evidence_gaps"] == []
    assert (
        "Regression deltas are still gated by same-condition comparability."
        in context["notes"]
    )
    assert regression_payload["mode"] == "same-condition"
    assert regression_payload["regression_detected"] is True
    assert "guard_analysis" not in regression_payload
    markdown = regression_md.read_text(encoding="utf-8")
    assert "## Runtime Telemetry Context" in markdown
    assert "edgeenv.runtime-telemetry-history.v1" in markdown


def test_cli_telemetry_replay_candidate_gap_to_regression_smoke(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(
            mean=100.0,
            p95=120.0,
            p99=130.0,
            fps=50.0,
            runtime_telemetry=_runtime_telemetry(sequence_id=1),
        ),
    )
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "candidate",
        _runner_result(mean=118.0, p95=132.0, p99=171.6, fps=39.0),
    )
    history_path = tmp_path / "runtime-telemetry-history.json"
    regression_json = tmp_path / "edgeenv-regression.json"
    regression_md = tmp_path / "edgeenv-regression.md"

    export_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "export-history",
            "--edgeenv-root",
            str(edgeenv_root),
            "--run-id",
            "baseline",
            "--run-id",
            "candidate",
            "--output",
            str(history_path),
        ],
    )
    inspect_result = runner.invoke(
        app,
        [
            "runs",
            "telemetry",
            "inspect-history",
            str(history_path),
        ],
    )
    regression_result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
            "--telemetry-history",
            str(history_path),
            "--output-json",
            str(regression_json),
            "--output-md",
            str(regression_md),
        ],
    )

    assert export_result.exit_code == 0, export_result.output
    assert "Telemetry entries: 1" in export_result.output
    assert "Missing telemetry: 1" in export_result.output
    assert inspect_result.exit_code == 0, inspect_result.output
    assert "Evidence gaps: 1" in inspect_result.output
    assert "Missing run IDs: candidate" in inspect_result.output
    assert regression_result.exit_code == 0, regression_result.output
    assert "- candidate: present=false, history=false" in regression_result.output
    assert "candidate: runtime_telemetry_missing_in_result" in regression_result.output
    assert "candidate: runtime_telemetry_missing" in regression_result.output

    regression_payload = json.loads(regression_json.read_text(encoding="utf-8"))
    context = regression_payload["runtime_telemetry_context"]
    assert context["candidate"]["result_telemetry_present"] is False
    assert context["candidate"]["history_entry_present"] is False
    assert context["candidate"]["history_missing_recorded"] is True
    assert context["candidate"]["history_missing_reason"] == "runtime_telemetry_missing"
    assert context["evidence_gaps"] == [
        {
            "run_id": "candidate",
            "reason": "runtime_telemetry_missing_in_result",
        },
        {
            "run_id": "candidate",
            "reason": "runtime_telemetry_missing",
        },
    ]
    markdown = regression_md.read_text(encoding="utf-8")
    assert "runtime_telemetry_missing_in_result" in markdown
    assert "runtime_telemetry_missing" in markdown


def test_committed_replay_fixtures_preserve_edgeenv_owned_context():
    candidate_gap = json.loads(
        (EXAMPLE_REGRESSION_DIR / "edgeenv_candidate_telemetry_gap.json").read_text(
            encoding="utf-8"
        )
    )
    sequence_inversion = json.loads(
        (EXAMPLE_REGRESSION_DIR / "edgeenv_sequence_inversion.json").read_text(
            encoding="utf-8"
        )
    )

    assert "guard_analysis" not in candidate_gap
    assert "guard_analysis" not in sequence_inversion
    assert candidate_gap["comparable"] is True
    assert sequence_inversion["mode"] == "same-condition"
    assert candidate_gap["regression_detected"] is False
    assert sequence_inversion["regression_detected"] is False

    candidate_context = candidate_gap["runtime_telemetry_context"]
    assert candidate_context["source"] == "result_artifacts+runtime_telemetry_history"
    assert candidate_context["history"]["summary"]["missing_telemetry_runs"] == 1
    assert candidate_context["candidate"]["result_telemetry_present"] is False
    assert candidate_context["candidate"]["history_entry_present"] is False
    assert candidate_context["candidate"]["history_missing_recorded"] is True
    assert candidate_context["candidate"]["history_missing_reason"] == (
        "runtime_telemetry_missing"
    )
    assert candidate_context["evidence_gaps"] == [
        {
            "run_id": "candidate",
            "reason": "runtime_telemetry_missing_in_result",
        },
        {
            "run_id": "candidate",
            "reason": "runtime_telemetry_missing",
        },
    ]

    sequence_context = sequence_inversion["runtime_telemetry_context"]
    assert sequence_context["history"]["summary"]["missing_telemetry_runs"] == 0
    assert sequence_context["baseline"]["execution_sequence_id"] == 5
    assert sequence_context["baseline"]["history_execution_sequence_id"] == 5
    assert sequence_context["candidate"]["execution_sequence_id"] == 2
    assert sequence_context["candidate"]["history_execution_sequence_id"] == 2
    assert sequence_context["evidence_gaps"] == []
    assert any(
        "not a comparability gate" in note
        for note in sequence_context["notes"]
    )

    regression = _load_regression_fixture("edgeenv_same_condition_regression.json")
    runtime_comparison = _load_regression_fixture(
        "edgeenv_runtime_comparison_blocked.json"
    )
    target_comparison = _load_regression_fixture(
        "edgeenv_target_comparison_blocked.json"
    )
    protocol_mismatch = _load_regression_fixture(
        "edgeenv_protocol_mismatch_blocked.json"
    )

    for fixture in (
        regression,
        runtime_comparison,
        target_comparison,
        protocol_mismatch,
    ):
        assert "guard_analysis" not in fixture
        assert "deployment_decision" not in fixture

    assert regression["comparable"] is True
    assert regression["mode"] == "same-condition"
    assert regression["regression_detected"] is True
    assert regression["regression_type"] == "mixed"
    assert regression["severity"] == "high"
    triggered = {
        item["name"] for item in regression["evidence"]["triggered_thresholds"]
    }
    assert {
        "mean_latency_review",
        "p99_latency_high",
        "fps_drop_review",
        "memory_peak_warning",
    } <= triggered
    regression_context = regression["runtime_telemetry_context"]
    assert regression_context["history"]["summary"]["history_seed_runs"] == 2
    assert regression_context["history"]["summary"][
        "history_seed_run_config_runs"
    ] == 2
    assert regression_context["baseline"]["history_seed_run_config"]["runs"] == 100
    assert regression_context["candidate"]["history_seed_run_config"][
        "input_mode"
    ] == "dummy"

    blocked_cases = [
        (runtime_comparison, "runtime-comparison", "review_as_runtime_comparison"),
        (target_comparison, "target-comparison", "review_as_target_comparison"),
        (protocol_mismatch, "protocol_mismatch", "rerun_with_matching_protocol"),
    ]
    delta_keys = {
        "mean_delta_pct",
        "p95_delta_pct",
        "p99_delta_pct",
        "fps_delta_pct",
        "memory_peak_delta_pct",
    }
    for fixture, mode, recommendation in blocked_cases:
        assert fixture["comparable"] is False
        assert fixture["mode"] == mode
        assert fixture["regression_detected"] is False
        assert fixture["regression_type"] == "not_evaluated"
        assert fixture["recommendation"] == recommendation
        assert not (delta_keys & set(fixture["evidence"]))


def test_regression_replay_fixture_matrix_matches_committed_reports():
    matrix = json.loads(
        (EXAMPLE_REGRESSION_DIR / "fixture_matrix.json").read_text(
            encoding="utf-8"
        )
    )
    assert matrix["schema_version"] == (
        "edgeenv-regression-replay-fixture-matrix-v1"
    )
    assert matrix["owner"] == "edgeenv"
    assert matrix["boundaries"] == {
        "not_a_deployment_decision": True,
        "not_a_guard_analysis": True,
        "not_production_monitoring": True,
        "comparability_first": True,
    }

    fixtures = matrix["fixtures"]
    roles = {entry["role"] for entry in fixtures}
    assert roles == set(matrix["required_roles"])

    delta_keys = {
        "mean_delta_pct",
        "p95_delta_pct",
        "p99_delta_pct",
        "fps_delta_pct",
        "memory_peak_delta_pct",
    }
    seen_modes = set()
    for entry in fixtures:
        payload = _load_regression_fixture(entry["path"])
        seen_modes.add(entry["mode"])

        assert "guard_analysis" not in payload
        assert "deployment_decision" not in payload
        assert payload["mode"] == entry["mode"]
        assert payload["comparable"] is entry["comparable"]
        assert payload["regression_detected"] is entry[
            "expected_regression_detected"
        ]
        assert payload["recommendation"] == entry["expected_recommendation"]

        evidence = payload["evidence"]
        if entry["regression_delta_allowed"]:
            assert delta_keys <= set(evidence)
        else:
            assert not (delta_keys & set(evidence))

        context = payload.get("runtime_telemetry_context")
        if entry["requires_runtime_telemetry_context"]:
            assert isinstance(context, dict)
            assert context["role"] == "supplemental_runtime_telemetry_context"
            assert any(
                "not a comparability gate" in note
                for note in context["notes"]
            )
        else:
            assert context is None

        if entry["requires_history_seed_run_config"]:
            assert context is not None
            summary = context["history"]["summary"]
            assert summary["history_seed_run_config_runs"] == 2
            assert context["baseline"]["history_seed_run_config"]["runs"] == 100
            assert context["candidate"]["history_seed_run_config"]["runs"] == 100

        if entry["telemetry_gap_expected"]:
            assert context is not None
            expected_gaps = set(entry["expected_evidence_gaps"])
            observed_gaps = {gap["reason"] for gap in context["evidence_gaps"]}
            assert expected_gaps <= observed_gaps

        if entry.get("sequence_context") == "inverted":
            assert context is not None
            assert context["baseline"]["execution_sequence_id"] > context[
                "candidate"
            ]["execution_sequence_id"]
            assert context["evidence_gaps"] == []

        expected_thresholds = set(entry.get("expected_triggered_thresholds", []))
        if expected_thresholds:
            observed_thresholds = {
                item["name"] for item in evidence["triggered_thresholds"]
            }
            assert expected_thresholds <= observed_thresholds

    assert {
        "same-condition",
        "runtime-comparison",
        "target-comparison",
        "protocol_mismatch",
    } <= seen_modes


def test_regression_cli_marks_runtime_comparison_not_evaluated(
    tmp_path,
    bench_config,
    target_profile,
):
    runner = CliRunner()
    edgeenv_root = tmp_path / ".edgeenv"
    _write_registered_run(
        edgeenv_root,
        bench_config,
        target_profile,
        "baseline",
        _runner_result(mean=100.0, p95=120.0, p99=130.0, fps=50.0),
    )
    changed = bench_config.model_copy(update={"runtime": "other-runtime"})
    _write_registered_run(
        edgeenv_root,
        changed,
        target_profile,
        "candidate",
        _runner_result(mean=118.0, p95=132.0, p99=171.6, fps=39.0),
    )

    result = runner.invoke(
        app,
        [
            "report",
            "regression",
            "baseline",
            "candidate",
            "--edgeenv-root",
            str(edgeenv_root),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Comparable: false" in result.output
    assert "Mode: runtime-comparison" in result.output
    assert "Regression detected: false" in result.output
    assert "Recommendation: review_as_runtime_comparison" in result.output
    assert "Regression Evidence: not evaluated" in result.output
    assert "mean_delta_pct" not in result.output


def _runner_result(
    *,
    mean: float,
    p95: float,
    p99: float,
    fps: float,
    memory_peak_mb: float | None = None,
    runtime_telemetry: dict | None = None,
) -> RunnerResult:
    return RunnerResult(
        latency_mean_ms=mean,
        latency_p50_ms=mean - 1.0,
        latency_p95_ms=p95,
        latency_p99_ms=p99,
        throughput_fps=fps,
        resource_metrics=(
            ResourceMetrics(memory_peak_mb=memory_peak_mb)
            if memory_peak_mb is not None
            else None
        ),
        runtime_telemetry=runtime_telemetry,
        stdout="stdout\n",
        stderr="",
    )


def _write_registered_run(
    edgeenv_root: Path,
    bench_config: BenchmarkConfig,
    target_profile: TargetProfile,
    run_id: str,
    runner_result: RunnerResult,
) -> None:
    config_path = edgeenv_root.parent / f"{run_id}-config.yaml"
    target_path = edgeenv_root.parent / f"{run_id}-target.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("name: test\n", encoding="utf-8")
    target_path.write_text("target_name: test\n", encoding="utf-8")
    result = make_result(
        bench_config,
        target_profile,
        run_id=run_id,
        runner_result=runner_result,
    )
    run_dir = ResultArtifactWriter(edgeenv_root).write(
        result=result,
        config_path=config_path,
        target_path=target_path,
        stdout="stdout\n",
        stderr="stderr\n",
    )
    RunRegistry(edgeenv_root / "runs.db").insert(result, run_dir / "result.json")


def _runtime_telemetry(
    sequence_id: int,
    *,
    missing_fields: list[str] | None = None,
) -> dict:
    missing = missing_fields or []
    expected_fields = ["gpu_temperature", "queue_depth", "telemetry_timestamp"]
    observed_fields = [field for field in expected_fields if field not in missing]
    return {
        "schema_version": "inferedge-runtime-telemetry-v1",
        "telemetry_timestamp": f"2026-05-22T00:00:0{sequence_id}Z",
        "execution_sequence_id": sequence_id,
        "latency": {
            "mean_ms": 100.0 + sequence_id,
            "p99_ms": 130.0 + sequence_id,
        },
        "resource": {
            "telemetry_source": "runtime-result",
        },
        "operation": {
            "timeout_observed": False,
        },
        "coverage": {
            "schema_version": "inferedge-runtime-telemetry-coverage-v1",
            "expected_fields": expected_fields,
            "observed_fields": observed_fields,
            "missing_fields": missing,
            "expected_field_count": len(expected_fields),
            "observed_field_count": len(observed_fields),
            "missing_field_count": len(missing),
            "coverage_ratio": round(len(observed_fields) / len(expected_fields), 6),
            "comparability_owner": "edgeenv",
            "missing_telemetry_is_failure": False,
        },
    }


def _runtime_history_seed(run_id: str, *, sequence_id: int) -> dict:
    return {
        "schema_version": "inferedge-runtime-telemetry-history-seed-v1",
        "evidence_role": "runtime_telemetry_history_seed",
        "run_id": run_id,
        "execution_sequence_id": sequence_id,
        "registry_owner": "edgeenv",
        "decision_owner": "lab",
        "replay_point": "after_runtime_result_export",
        "run_config": {
            "batch": 1,
            "height": 224,
            "width": 224,
            "warmup": 10,
            "runs": 100,
            "timeout_ms": None,
            "input_mode": "dummy",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown",
        },
    }


def _load_regression_fixture(name: str) -> dict:
    return json.loads(
        (EXAMPLE_REGRESSION_DIR / name).read_text(encoding="utf-8")
    )


def _orchestrator_context(run_id: str) -> dict:
    return {
        "schema_version": "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1",
        "role": "orchestrator_operation_context_for_edgeenv",
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
        "source": "orchestration_summary",
        "run_id": run_id,
        "not_a_regression_judgement": True,
        "not_a_comparability_gate": True,
        "decision_owner": "lab",
        "regression_owner": "edgeenv",
        "candidate_context": {
            "run_id": run_id,
            "telemetry_source": "inferedge_orchestrator_operation_summary",
            "queue_depth": 7,
            "operation": {
                "queue_depth": 7,
                "deadline_missed_count": 2,
                "fallback_count": 1,
            },
            "resource": {
                "source": "tegrastats_timeline",
                "gpu_temperature": 78.5,
                "ram_used_mb": 2048.0,
            },
        },
        "edgeenv_mapping_hint": {
            "runtime_telemetry_context_role": "candidate",
            "copy_candidate_context_to": ORCHESTRATOR_EDGEENV_CANDIDATE_CONTEXT_PATH,
            "operation_context_role": ORCHESTRATOR_EDGEENV_OPERATION_CONTEXT_ROLE,
            "coverage_summary_owner": ORCHESTRATOR_EDGEENV_COVERAGE_SUMMARY_OWNER,
            "coverage_summary_path": ORCHESTRATOR_EDGEENV_HISTORY_COVERAGE_PATH,
            "candidate_context_required_fields": [
                "run_id",
                "telemetry_source",
                "operation",
                "resource",
            ],
            "aiguard_evidence_candidates": [
                *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            ],
        },
    }
