from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from inferedge_env.cli import app
from inferedge_env.result.lab_handoff import (
    LAB_BUNDLE_EXPECTED_REPORT_MARKERS,
    LAB_BUNDLE_OPTIONAL_AIGUARD_SOURCE_TRACEABILITY_CONTEXT_ROLE,
    LAB_BUNDLE_OPTIONAL_AIGUARD_STALE_DROP_REPRODUCTION_COMMAND,
    RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION,
    RuntimeIntelligenceLabHandoffError,
    build_runtime_intelligence_lab_handoff_manifest,
)
from inferedge_env.result.telemetry_history import (
    ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES,
    ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE,
    ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
    ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
    ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_TRACEABILITY_SMOKE = (
    REPO_ROOT / "scripts" / "smoke_runtime_intelligence_source_traceability.sh"
)
REPLAY_REGRESSION_HANDOFF_SMOKE = (
    REPO_ROOT
    / "scripts"
    / "smoke_runtime_intelligence_replay_regression_handoff.sh"
)
RELEASE_QUALITY_GATE_SMOKE = (
    REPO_ROOT / "scripts" / "smoke_release_quality_gate.sh"
)


def test_runtime_intelligence_lab_handoff_manifest_records_producer_contracts(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )

    payload = build_runtime_intelligence_lab_handoff_manifest(
        baseline_result_path=baseline_path,
        candidate_result_path=candidate_path,
        edgeenv_regression_report_path=regression_path,
        telemetry_history_path=history_path,
    )

    assert payload["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert payload["files"] == {
        "baseline_result": str(baseline_path),
        "candidate_result": str(candidate_path),
        "edgeenv_regression_report": str(regression_path),
        "runtime_telemetry_history": str(history_path),
    }
    assert payload["source_repositories"] == {
        "runtime_result": "InferEdge-Runtime",
        "edgeenv_regression_report": "InferEdgeEnv",
        "orchestrator_operation_context": "InferEdgeOrchestrator",
        "lab_report_owner": "InferEdgeLab",
    }
    assert payload["artifact_roles"]["edgeenv_regression_report"] == (
        "edgeenv-comparability-first-runtime-regression-report"
    )
    assert payload["producer_contracts"] == {
        "runtime_result_contract": "lab-compatible-runtime-result-json",
        "edgeenv_history_schema": "edgeenv.runtime-telemetry-history.v1",
        "runtime_telemetry_history_seed_schema": (
            "inferedge-runtime-telemetry-history-seed-v1"
        ),
        "orchestrator_feed_schema": (
            "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1"
        ),
    }
    assert payload["lab_bundle_alignment"]["bundle_schema_version"] == (
        "inferedge.runtime-intelligence-artifact-bundle.v1"
    )
    assert payload["lab_bundle_alignment"]["required_file_keys"] == [
        "baseline_result",
        "candidate_result",
        "edgeenv_regression_report",
        "aiguard_guard_analysis",
    ]
    assert payload["lab_bundle_alignment"]["edgeenv_produced_file_keys"] == [
        "baseline_result",
        "candidate_result",
        "edgeenv_regression_report",
        "runtime_telemetry_history",
    ]
    assert payload["lab_bundle_alignment"]["external_file_keys"] == [
        "aiguard_guard_analysis"
    ]
    assert payload["lab_bundle_alignment"]["source_repositories"][
        "aiguard_guard_analysis"
    ] == "InferEdgeAIGuard"
    assert payload["lab_bundle_alignment"]["artifact_roles"][
        "aiguard_guard_analysis"
    ] == "aiguard-deterministic-runtime-anomaly-evidence"
    assert payload["lab_bundle_alignment"]["producer_contracts"][
        "aiguard_schema"
    ] == "inferedge-aiguard-diagnosis-v1"
    assert payload["lab_bundle_alignment"][
        "external_aiguard_required_evidence_types"
    ] == [
        "runtime_telemetry_context_coverage",
        "edgeenv_orchestrator_producer_lineage",
        "edgeenv_orchestrator_operation_risk_rollup",
        "edgeenv_orchestrator_task_event_rollup",
        "edgeenv_orchestrator_operation_timeline_summary",
        "edgeenv_orchestrator_scheduler_fairness_summary",
        "edgeenv_orchestrator_policy_pressure_summary",
        "runtime_history_seed_run_config_traceability",
        "runtime_queue_overload",
        "runtime_thermal_instability",
        "remote_execution_recovered_by_fallback",
    ]
    assert payload["lab_bundle_alignment"]["optional_aiguard_evidence_types"] == [
        "stale_frame_risk",
        "edgeenv_orchestrator_stale_drop_summary",
    ]
    assert payload["lab_bundle_alignment"]["optional_aiguard_source_traceability"] == {
        "context_role": "read_only_optional_source_traceability",
        "edgeenv_does_not_generate_guard_analysis": True,
        "lab_is_final_decision_owner": True,
        "optional_present_source_artifact": {
            "repository": "InferEdgeAIGuard",
            "path": (
                "examples/runtime_intelligence/"
                "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
            ),
            "schema_version": "inferedge-aiguard-diagnosis-v1",
            "role": "aiguard-optional-stale-drop-full-evidence-source",
            "context_role": "read_only_cross_repo_traceability",
            "reproduction_command": [
                "python",
                "-m",
                "inferedge_aiguard.cli",
                "build-runtime-intelligence-optional-stale-drop",
                "--edgeenv-regression",
                (
                    "examples/runtime_intelligence/"
                    "edgeenv_runtime_regression_with_optional_stale_drop_context.json"
                ),
                "--remote-dispatch",
                (
                    "examples/runtime_intelligence/"
                    "remote_dispatch_fallback_recovered_result.json"
                ),
                "--orchestration-summary",
                (
                    "examples/runtime_intelligence/"
                    "orchestrator_multi_workload_sustained_summary.json"
                ),
                "--save-json",
                (
                    "examples/runtime_intelligence/"
                    "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
                ),
            ],
        },
    }
    assert payload["lab_bundle_alignment"]["expected_report_markers"] == list(
        LAB_BUNDLE_EXPECTED_REPORT_MARKERS
    )
    assert payload["lab_bundle_alignment"]["external_aiguard_alignment_gate"] == {
        "declared_by": "edgeenv",
        "guard_analysis_file_key": "aiguard_guard_analysis",
        "validated_by": [
            "inferedge-aiguard check-edgeenv-handoff-alignment",
            "inferedgelab runtime-intelligence bundle manifest gate",
        ],
        "edgeenv_does_not_generate_guard_analysis": True,
        "lab_is_final_decision_owner": True,
    }
    assert payload["lab_bundle_alignment"]["boundary_flags"] == {
        "orchestrator_context_is_verdict": False,
        "orchestrator_context_is_comparability_gate": False,
        "aiguard_guard_analysis_is_external": True,
        "aiguard_is_final_decision_owner": False,
        "edgeenv_does_not_generate_guard_analysis": True,
        "lab_is_final_decision_owner": True,
        "production_observability_platform": False,
    }
    assert payload["boundaries"]["orchestrator_context_is_verdict"] is False
    assert payload["boundaries"]["lab_is_final_decision_owner"] is True
    assert payload["edgeenv_report_summary"] == {
        "baseline_run_id": "baseline",
        "candidate_run_id": "candidate",
        "comparable": True,
        "mode": "same-condition",
        "regression_detected": True,
        "regression_type": "mixed",
        "severity": "high",
        "fixture_matrix_context_present": True,
        "fixture_matrix_schema_version": "edgeenv-regression-replay-fixture-matrix-v1",
        "fixture_matrix_owner": "edgeenv",
        "fixture_matrix_required_role_count": 2,
        "fixture_matrix_covered_role_count": 2,
        "fixture_matrix_covered_modes": [
            "same-condition",
            "protocol_mismatch",
        ],
        "fixture_matrix_comparability_first": True,
        "fixture_matrix_not_a_deployment_decision": True,
        "runtime_telemetry_context_present": True,
        "history_seed_runs": 2,
        "history_seed_run_config_runs": 2,
        "history_seed_run_config_marker_fields": [
            "input_mode",
            "input_preprocess",
            "power_mode",
            "jetson_clocks",
            "warmup",
            "runs",
        ],
        "history_seed_run_config_markers": [
            {
                "run_id": "baseline",
                "shape": "1x640x640",
                "input_mode": "dummy",
                "input_preprocess": "none",
                "power_mode": "unknown",
                "jetson_clocks": "unknown",
                "warmup": 1,
                "runs": 10,
            },
            {
                "run_id": "candidate",
                "shape": "1x640x640",
                "input_mode": "dummy",
                "input_preprocess": "none",
                "power_mode": "unknown",
                "jetson_clocks": "unknown",
                "warmup": 1,
                "runs": 10,
            },
        ],
        "orchestrator_context_present": True,
        "device_local_producer_context_present": True,
        "device_local_producer_context_run_ids": ["candidate"],
        "producer_lineage_guard_alignment_present": True,
        "producer_lineage_guard_alignment_run_ids": ["candidate"],
        "orchestrator_operation_risk_rollup_present": True,
        "orchestrator_operation_risk_rollup_run_ids": ["candidate"],
        "orchestrator_task_event_rollup_present": True,
        "orchestrator_task_event_rollup_run_ids": ["candidate"],
        "orchestrator_operation_timeline_summary_present": True,
        "orchestrator_operation_timeline_summary_run_ids": ["candidate"],
        "orchestrator_policy_pressure_summary_present": True,
        "orchestrator_policy_pressure_summary_run_ids": ["candidate"],
        "orchestrator_stale_drop_summary_present": True,
        "orchestrator_stale_drop_summary_run_ids": ["candidate"],
        "duration_traceability_present": True,
        "duration_traceability_run_ids": ["candidate"],
        "duration_sources": ["entrypoint_requested_frames"],
        "duration_scope_labels": [
            "source=entrypoint_requested_frames, "
            "label=short 96-frame-class replay (96 frames), "
            "class=short_96_frame_class, frames=96",
        ],
    }
    assert "AIGuard guard_analysis is intentionally not produced by EdgeEnv." in (
        payload["notes"]
    )


def test_runtime_intelligence_docs_describe_lab_expected_report_markers():
    docs = [
        (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs" / "ko" / "README.md").read_text(encoding="utf-8"),
        (REPO_ROOT / "docs" / "portfolio_summary.md").read_text(
            encoding="utf-8"
        ),
    ]

    for doc in docs:
        assert "lab_bundle_alignment.expected_report_markers" in doc
        assert "optional_aiguard_source_traceability" in doc
        assert "smoke_runtime_intelligence_source_traceability.sh" in doc
        assert "smoke_runtime_intelligence_replay_regression_handoff.sh" in doc
        assert "build-runtime-intelligence-optional-stale-drop" in doc
        assert (
            "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
            in doc
        )
        assert "agent_scheduler_delay_sample.json" in doc
        assert "remote_fallback_recovery_sample.json" in doc
        assert "scheduler_delay_pattern" in doc
        assert "remote_execution_recovered_by_fallback" in doc
        assert "EdgeEnv benchmark" in doc
        assert "deployment input" in doc
        for marker in LAB_BUNDLE_EXPECTED_REPORT_MARKERS:
            assert marker in doc


def test_runtime_intelligence_source_traceability_smoke_script_help():
    result = subprocess.run(
        ["bash", str(SOURCE_TRACEABILITY_SMOKE), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Runtime Intelligence source traceability smoke" in result.stdout
    assert "read-only optional AIGuard source artifact" in result.stdout


def test_runtime_intelligence_source_traceability_smoke_script_runs(tmp_path):
    output_dir = tmp_path / "runtime_intelligence_source_traceability"

    result = subprocess.run(
        [
            "bash",
            str(SOURCE_TRACEABILITY_SMOKE),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "EdgeEnv Runtime Intelligence source traceability smoke passed."
        in result.stdout
    )
    handoff = json.loads(
        (
            output_dir
            / "edgeenv_runtime_intelligence_lab_handoff_source_traceability.json"
        ).read_text(encoding="utf-8")
    )
    assert handoff["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert "guard_analysis" not in handoff
    alignment = handoff["lab_bundle_alignment"]
    assert "aiguard_guard_analysis" in alignment["external_file_keys"]
    assert "aiguard_guard_analysis" not in alignment["edgeenv_produced_file_keys"]
    traceability = alignment["optional_aiguard_source_traceability"]
    assert traceability["context_role"] == (
        LAB_BUNDLE_OPTIONAL_AIGUARD_SOURCE_TRACEABILITY_CONTEXT_ROLE
    )
    assert traceability["edgeenv_does_not_generate_guard_analysis"] is True
    assert traceability["lab_is_final_decision_owner"] is True
    source_artifact = traceability["optional_present_source_artifact"]
    assert source_artifact["repository"] == "InferEdgeAIGuard"
    assert source_artifact["path"] == (
        "examples/runtime_intelligence/"
        "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
    )
    assert source_artifact["schema_version"] == "inferedge-aiguard-diagnosis-v1"
    assert source_artifact["context_role"] == "read_only_cross_repo_traceability"
    assert source_artifact["reproduction_command"] == list(
        LAB_BUNDLE_OPTIONAL_AIGUARD_STALE_DROP_REPRODUCTION_COMMAND
    )

    summary = (
        output_dir
        / "edgeenv_runtime_intelligence_source_traceability_smoke_summary.md"
    ).read_text(encoding="utf-8")
    assert "- Status: passed" in summary
    assert "optional_aiguard_source_traceability: preserved" in summary
    assert (
        "optional_present_source_artifact: "
        "InferEdgeAIGuard/examples/runtime_intelligence/"
        "aiguard_runtime_operation_guard_analysis_optional_stale_drop.json"
    ) in summary
    assert (
        "optional_present_reproduction_command: "
        "python -m inferedge_aiguard.cli build-runtime-intelligence-optional-stale-drop"
    ) in summary
    assert (
        "lab_source_traceability_gate: passed" in summary
        or "lab_source_traceability_gate: skipped" in summary
    )

    lab_summary = output_dir / "lab_source_traceability_summary.md"
    if lab_summary.exists():
        lab_summary_text = lab_summary.read_text(encoding="utf-8")
        assert "- Status: passed" in lab_summary_text
        assert "## Validated Source Traceability" in lab_summary_text


def test_runtime_intelligence_replay_regression_handoff_smoke_script_help():
    result = subprocess.run(
        ["bash", str(REPLAY_REGRESSION_HANDOFF_SMOKE), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Runtime Intelligence replay/regression/handoff smoke" in result.stdout
    assert "--python <path>" in result.stdout
    assert "same-condition comparability" in result.stdout


def test_release_quality_gate_runs_runtime_intelligence_replay_smoke():
    script = RELEASE_QUALITY_GATE_SMOKE.read_text(encoding="utf-8")
    assert "runtime intelligence replay/regression/handoff" in script
    assert "smoke_runtime_intelligence_replay_regression_handoff.sh" in script
    assert "--python \"$python_bin\"" in script
    assert "runtime_intelligence_replay_regression_handoff_summary.md" in script


def test_runtime_intelligence_replay_regression_handoff_smoke_script_runs(
    tmp_path,
):
    output_dir = tmp_path / "runtime_intelligence_replay_regression_handoff"

    result = subprocess.run(
        [
            "bash",
            str(REPLAY_REGRESSION_HANDOFF_SMOKE),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (
        "EdgeEnv Runtime Intelligence replay/regression/handoff smoke passed."
        in result.stdout
    )
    summary = (
        output_dir
        / "runtime_intelligence_replay_regression_handoff_summary.md"
    ).read_text(encoding="utf-8")
    assert "- Status: passed" in summary
    assert "- telemetry_runs: 2" in summary
    assert "- history_seed_runs: 2" in summary
    assert "- history_seed_run_config_runs: 2" in summary
    assert "- regression_mode: same-condition" in summary
    assert "- triggered_threshold: p99_latency_high" in summary
    assert "- edgeenv_does_not_generate_guard_analysis: true" in summary
    assert "- lab_is_final_decision_owner: true" in summary

    history = json.loads(
        (output_dir / "runtime_telemetry_history.json").read_text(
            encoding="utf-8"
        )
    )
    assert history["schema_version"] == "edgeenv.runtime-telemetry-history.v1"
    assert history["summary"]["telemetry_runs"] == 2
    assert history["summary"]["history_seed_runs"] == 2
    assert history["summary"]["history_seed_run_config_runs"] == 2
    assert history["summary"]["missing_telemetry_runs"] == 0

    regression = json.loads(
        (output_dir / "edgeenv_runtime_regression.json").read_text(
            encoding="utf-8"
        )
    )
    assert regression["mode"] == "same-condition"
    assert regression["regression_detected"] is True
    assert "guard_analysis" not in regression
    triggered = {
        item["name"]
        for item in regression["evidence"]["triggered_thresholds"]
    }
    assert "p99_latency_high" in triggered
    context = regression["runtime_telemetry_context"]
    assert context["role"] == "supplemental_runtime_telemetry_context"
    assert context["history"]["summary"]["history_seed_run_config_runs"] == 2
    assert (
        "Regression deltas are still gated by same-condition comparability."
        in context["notes"]
    )

    handoff = json.loads(
        (
            output_dir / "edgeenv_runtime_intelligence_lab_handoff.json"
        ).read_text(encoding="utf-8")
    )
    assert handoff["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert "guard_analysis" not in handoff
    assert "runtime_telemetry_history" in handoff["files"]
    assert handoff["edgeenv_report_summary"]["history_seed_runs"] == 2
    assert handoff["edgeenv_report_summary"][
        "history_seed_run_config_runs"
    ] == 2
    assert handoff["edgeenv_report_summary"][
        "history_seed_run_config_markers"
    ]
    alignment = handoff["lab_bundle_alignment"]
    assert "aiguard_guard_analysis" in alignment["external_file_keys"]
    assert "aiguard_guard_analysis" not in alignment["edgeenv_produced_file_keys"]
    assert (
        alignment["boundary_flags"]["edgeenv_does_not_generate_guard_analysis"]
        is True
    )
    assert alignment["boundary_flags"]["lab_is_final_decision_owner"] is True


def test_readmes_expose_edgeenv_role_boundaries():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_ko = (REPO_ROOT / "docs" / "ko" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "Language: English | [한국어](docs/ko/README.md)" in readme
    assert "Language: [English](../../README.md) | 한국어" in readme_ko

    for required in [
        "## Role Boundary At A Glance",
        "Stores local artifacts, SQLite registry rows, portable bundles",
        "protocol-mismatch boundaries before metric deltas",
        "overwrite Lab `deployment_decision`",
        "production observability platform",
        "remote execution proof",
    ]:
        assert required in readme

    for required in [
        "## 역할 경계 한눈에 보기",
        "local artifact, SQLite registry row, portable bundle",
        "protocol-mismatch 경계를 판정한다",
        "Lab `deployment_decision`을 덮어쓰거나",
        "production observability platform",
        "remote execution proof가 되지 않는다",
    ]:
        assert required in readme_ko


def test_runtime_regression_korean_quick_guide_links_and_boundaries():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_ko = (REPO_ROOT / "docs" / "ko" / "README.md").read_text(
        encoding="utf-8"
    )
    language = (REPO_ROOT / "docs" / "language.md").read_text(encoding="utf-8")
    guide = (
        REPO_ROOT / "docs" / "ko" / "runtime-regression-monitor.md"
    ).read_text(encoding="utf-8")

    assert (
        "[한국어 Runtime Regression Monitor Quick Guide]"
        "(docs/ko/runtime-regression-monitor.md)"
        in readme
    )
    assert (
        "[Runtime Regression Monitor 한국어 Quick Guide]"
        "(runtime-regression-monitor.md)"
        in readme_ko
    )
    assert "ko/runtime-regression-monitor.md" in language
    assert (
        "Language: [English representative]"
        "(../compare-workflow-guide.md#runtime-regression-report) | 한국어"
        in guide
    )

    for required in [
        "local-first run evidence",
        "comparability checker",
        "comparability-first",
        "`same-condition`",
        "`runtime-comparison`",
        "`target-comparison`",
        "`protocol_mismatch`",
        "Lab `deployment_decision`",
        "AIGuard `guard_analysis`",
        "Orchestrator scheduler",
        "production observability platform",
        "general monitoring SaaS",
        "public leaderboard",
        "Real-time data drift",
        "Jetson 필요 여부",
    ]:
        assert required in guide


def test_runtime_intelligence_lab_handoff_cli_writes_manifest(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    output_path = tmp_path / "edgeenv-lab-handoff.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "report",
            "runtime-intelligence-handoff",
            "--baseline-result",
            str(baseline_path),
            "--candidate-result",
            str(candidate_path),
            "--edgeenv-regression-report",
            str(regression_path),
            "--telemetry-history",
            str(history_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Runtime Intelligence handoff manifest written" in result.output
    assert "Lab remains the final deployment decision owner." in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == RUNTIME_INTELLIGENCE_LAB_HANDOFF_SCHEMA_VERSION
    assert payload["edgeenv_report_summary"]["history_seed_runs"] == 2
    assert payload["edgeenv_report_summary"]["history_seed_run_config_runs"] == 2
    assert "History seed entries: 2" in result.output
    assert "History seed run_config markers: baseline, candidate" in result.output
    assert "Device-local producer contexts: candidate" in result.output
    assert "Producer-lineage guard alignment: candidate" in result.output
    assert "Orchestrator operation risk rollup: candidate" in result.output
    assert "Orchestrator operation timeline summary: candidate" in result.output
    assert "Orchestrator policy-pressure summary: candidate" in result.output
    assert "Orchestrator stale-drop summary: candidate" in result.output
    assert (
        "External AIGuard evidence types: runtime_telemetry_context_coverage, "
        "edgeenv_orchestrator_producer_lineage, "
        "edgeenv_orchestrator_operation_risk_rollup, "
        "edgeenv_orchestrator_task_event_rollup, "
        "edgeenv_orchestrator_operation_timeline_summary, "
        "edgeenv_orchestrator_scheduler_fairness_summary, "
        "edgeenv_orchestrator_policy_pressure_summary, "
        "runtime_history_seed_run_config_traceability, "
        "runtime_queue_overload, runtime_thermal_instability, "
        "remote_execution_recovered_by_fallback"
    ) in result.output


def test_runtime_intelligence_lab_handoff_accepts_legacy_results_without_run_id(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    baseline_path.write_text(json.dumps({}), encoding="utf-8")
    candidate_path.write_text(json.dumps({}), encoding="utf-8")

    payload = build_runtime_intelligence_lab_handoff_manifest(
        baseline_result_path=baseline_path,
        candidate_result_path=candidate_path,
        edgeenv_regression_report_path=regression_path,
        telemetry_history_path=history_path,
    )

    assert payload["edgeenv_report_summary"]["baseline_run_id"] == "baseline"
    assert payload["edgeenv_report_summary"]["candidate_run_id"] == "candidate"


def test_runtime_intelligence_lab_handoff_rejects_mismatched_run_id(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["candidate_run_id"] = "other-candidate"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_run_id does not match",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_history_seed(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    candidate_seed = regression["runtime_telemetry_context"]["history"]["runs"][1][
        "runtime_telemetry_history_seed"
    ]
    candidate_seed["registry_owner"] = "runtime"
    candidate_seed["decision_owner"] = "aiguard"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="registry_owner must be edgeenv",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_seed_count_mismatch(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["history"]["summary"][
        "history_seed_runs"
    ] = 1
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="history_seed_runs must match preserved seed count",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_seed_run_config(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    candidate_seed = regression["runtime_telemetry_context"]["history"]["runs"][1][
        "runtime_telemetry_history_seed"
    ]
    candidate_seed["run_config"]["runs"] = "10"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=r"run_config\.runs must be an integer",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_history_seed_run_config(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    candidate_seed = history["runs"][1]["runtime_telemetry_history_seed"]
    candidate_seed["run_config"]["timeout_ms"] = "5000"
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=r"run_config\.timeout_ms must be an integer or null",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_schema(tmp_path):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["schema_version"] = "unknown"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="orchestrator_operation_context.schema_version",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_producer_marker(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["artifact_role"] = "lab-owned-deployment-risk-report"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="artifact_role must be orchestrator-supplemental-operation-context",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_orchestrator_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["coverage_summary_owner"] = "orchestrator"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="coverage_summary_owner must be edgeenv",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_incomplete_mapping_required_fields(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["candidate_context_required_fields"] = [
        "run_id",
        "operation",
        "resource",
    ]
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_context_required_fields must include telemetry_source",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_incomplete_aiguard_candidates(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["edgeenv_mapping_hint"]["aiguard_evidence_candidates"] = [
        "runtime_queue_overload"
    ]
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="aiguard_evidence_candidates must include runtime_thermal_instability",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_missing_guard_alignment(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ].pop("downstream_guard_alignment")
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="downstream_guard_alignment must be an object",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_guard_alignment(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["downstream_guard_alignment"][
        "producer_lineage_evidence_type"
    ] = "runtime_queue_overload"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=(
            "producer_lineage_evidence_type must be "
            "edgeenv_orchestrator_producer_lineage"
        ),
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_missing_device_local_producer(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"].pop("producer")
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer is required for device-local lineage",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_unmapped_regression_device_source(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    producer = regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["producer"]
    producer["producer_sources_by_task"] = {
        "vision_agent": ["orchestration_summary"],
    }
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match=(
            "device_local_producer_sources must also appear in "
            "producer_sources_by_task"
        ),
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_regression_stage_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    producer = regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["producer"]
    producer["producer_stage_by_task"] = {"vision_agent": ""}
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer_stage_by_task.vision_agent must be a non-empty string",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_history_missing_device_local_producer(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history["runs"][1]["orchestrator_operation_context"]["candidate_context"].pop(
        "producer"
    )
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="candidate_context.producer is required",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_bad_history_stage_mapping(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    history = json.loads(history_path.read_text(encoding="utf-8"))
    producer = history["runs"][1]["orchestrator_operation_context"][
        "candidate_context"
    ]["producer"]
    producer["producer_stage_by_task"] = {"vision_agent": ""}
    history_path.write_text(json.dumps(history), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="producer_stage_by_task.vision_agent must be a non-empty string",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_stale_drop_summary_as_decision(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["operation"]["stale_drop_summary"][
        "decision_owner"
    ] = "aiguard"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="stale_drop_summary.decision_owner must be lab",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def test_runtime_intelligence_lab_handoff_rejects_policy_pressure_as_decision(
    tmp_path,
):
    baseline_path, candidate_path, regression_path, history_path = _write_handoff_files(
        tmp_path
    )
    regression = json.loads(regression_path.read_text(encoding="utf-8"))
    regression["runtime_telemetry_context"]["candidate"][
        "orchestrator_operation_context"
    ]["candidate_context"]["operation"]["policy_pressure_summary"][
        "decision_owner"
    ] = "aiguard"
    regression_path.write_text(json.dumps(regression), encoding="utf-8")

    with pytest.raises(
        RuntimeIntelligenceLabHandoffError,
        match="policy_pressure_summary.decision_owner must be lab",
    ):
        build_runtime_intelligence_lab_handoff_manifest(
            baseline_result_path=baseline_path,
            candidate_result_path=candidate_path,
            edgeenv_regression_report_path=regression_path,
            telemetry_history_path=history_path,
        )


def _write_handoff_files(tmp_path):
    baseline_path = tmp_path / "baseline-result.json"
    candidate_path = tmp_path / "candidate-result.json"
    regression_path = tmp_path / "edgeenv-regression.json"
    history_path = tmp_path / "runtime-telemetry-history.json"
    baseline_path.write_text(json.dumps({"run_id": "baseline"}), encoding="utf-8")
    candidate_path.write_text(json.dumps({"run_id": "candidate"}), encoding="utf-8")
    operation_context = _orchestrator_operation_context("candidate")
    history_path.write_text(
        json.dumps(
            {
                "schema_version": "edgeenv.runtime-telemetry-history.v1",
                "summary": {
                    "registered_runs": 2,
                    "telemetry_runs": 2,
                    "missing_telemetry_runs": 0,
                    "orchestrator_feed_runs": 1,
                    "history_seed_runs": 2,
                    "history_seed_run_config_runs": 2,
                },
                "runs": [
                    {
                        "run_id": "baseline",
                        "runtime_telemetry_history_seed": _runtime_history_seed(
                            "baseline",
                            sequence_id=1,
                        ),
                    },
                    {
                        "run_id": "candidate",
                        "runtime_telemetry_history_seed": _runtime_history_seed(
                            "candidate",
                            sequence_id=2,
                        ),
                        "orchestrator_operation_context": operation_context,
                    },
                ],
                "missing_telemetry": [],
            }
        ),
        encoding="utf-8",
    )
    regression_path.write_text(
        json.dumps(
            {
                "baseline_run_id": "baseline",
                "candidate_run_id": "candidate",
                "comparable": True,
                "mode": "same-condition",
                "regression_detected": True,
                "regression_type": "mixed",
                "severity": "high",
                "fixture_matrix_context": _fixture_matrix_context(),
                "runtime_telemetry_context": {
                    "history": {
                        "schema_version": "edgeenv.runtime-telemetry-history.v1",
                        "summary": {
                            "registered_runs": 2,
                            "telemetry_runs": 2,
                            "missing_telemetry_runs": 0,
                            "orchestrator_feed_runs": 1,
                            "history_seed_runs": 2,
                            "history_seed_run_config_runs": 2,
                        },
                        "runs": [
                            {
                                "run_id": "baseline",
                                "runtime_telemetry_history_seed": (
                                    _runtime_history_seed(
                                        "baseline",
                                        sequence_id=1,
                                    )
                                ),
                            },
                            {
                                "run_id": "candidate",
                                "duration_source": "entrypoint_requested_frames",
                                "duration_scope_label": (
                                    "source=entrypoint_requested_frames, "
                                    "label=short 96-frame-class replay (96 frames), "
                                    "class=short_96_frame_class, frames=96"
                                ),
                                "runtime_telemetry_history_seed": (
                                    _runtime_history_seed(
                                        "candidate",
                                        sequence_id=2,
                                    )
                                ),
                                "orchestrator_operation_context": operation_context,
                            },
                        ],
                    },
                    "baseline": {"run_id": "baseline"},
                    "candidate": {
                        "run_id": "candidate",
                        "duration_source": "entrypoint_requested_frames",
                        "duration_scope_label": (
                            "source=entrypoint_requested_frames, "
                            "label=short 96-frame-class replay (96 frames), "
                            "class=short_96_frame_class, frames=96"
                        ),
                        "orchestrator_operation_context": operation_context,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return baseline_path, candidate_path, regression_path, history_path


def _fixture_matrix_context() -> dict:
    return {
        "schema_version": "edgeenv-regression-replay-fixture-matrix-v1",
        "owner": "edgeenv",
        "required_role_count": 2,
        "covered_role_count": 2,
        "required_roles": [
            "same_condition_regression",
            "protocol_mismatch_blocked",
        ],
        "covered_roles": [
            "same_condition_regression",
            "protocol_mismatch_blocked",
        ],
        "covered_modes": [
            "same-condition",
            "protocol_mismatch",
        ],
        "boundaries": {
            "comparability_first": True,
            "not_a_deployment_decision": True,
            "not_a_guard_analysis": True,
        },
    }


def _orchestrator_operation_context(run_id: str) -> dict:
    return {
        "schema_version": "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1",
        "source_repository": ORCHESTRATOR_TELEMETRY_FEED_SOURCE_REPOSITORY,
        "artifact_role": ORCHESTRATOR_TELEMETRY_FEED_ARTIFACT_ROLE,
        "producer_contract": ORCHESTRATOR_TELEMETRY_FEED_PRODUCER_CONTRACT,
        "not_a_regression_judgement": True,
        "not_a_comparability_gate": True,
        "decision_owner": "lab",
        "regression_owner": "edgeenv",
        "candidate_context": {
            "run_id": run_id,
            "telemetry_source": "inferedge_orchestrator_operation_summary",
            "operation": {
                "queue_depth": 7,
                "stale_drop_summary": _stale_drop_summary_payload(),
                "runtime_task_event_summary": {
                    "vision_agent": {
                        "scheduler_delay_event_count": 1,
                        "deadline_missed_count": 1,
                        "fallback_decision_count": 0,
                        "max_scheduler_delay_cycles": 3,
                        "max_queue_wait_ms": 15.0,
                        "policy_decision_reason_counts": {
                            "queue_backlog_threshold_exceeded": 1,
                        },
                        "drop_reason_counts": {},
                    },
                    "voice_command_agent": {
                        "scheduler_delay_event_count": 0,
                        "deadline_missed_count": 0,
                        "fallback_decision_count": 1,
                        "max_scheduler_delay_cycles": 0,
                        "max_queue_wait_ms": 0.0,
                        "policy_decision_reason_counts": {
                            "queue_backlog_threshold_exceeded": 1,
                        },
                        "drop_reason_counts": {
                            "load_shedding_backlog_threshold_exceeded": 1,
                        },
                    },
                },
                "tasks_with_deadline_miss": ["vision_agent"],
                "tasks_with_fallback": ["voice_command_agent"],
                "tasks_with_scheduler_delay": ["vision_agent"],
                "operation_risk_rollup": _operation_risk_rollup_payload(),
                "policy_pressure_summary": _policy_pressure_summary_payload(),
                "operation_timeline_summary": _operation_timeline_summary_payload(),
            },
            "resource": {"source": "tegrastats_timeline"},
            "producer": {
                "operation_context_role": "supplemental",
                "producer_sources": [
                    "device_local_cli_override",
                    "orchestration_summary",
                ],
                "device_local_producer_sources": ["device_local_cli_override"],
                "producer_sources_by_task": {
                    "vision_agent": ["device_local_cli_override"],
                },
                "producer_stage_by_task": {
                    "vision_agent": "device_local_starter",
                },
                "producer_event_count": 4,
                "device_local_event_count": 2,
                "device_local_task_count": 1,
            },
        },
        "edgeenv_mapping_hint": {
            "runtime_telemetry_context_role": "candidate",
            "copy_candidate_context_to": "runtime_telemetry_context.candidate",
            "operation_context_role": "supplemental",
            "coverage_summary_owner": "edgeenv",
            "coverage_summary_path": (
                "runtime_telemetry_context.history.telemetry_coverage"
            ),
            "candidate_context_required_fields": [
                "run_id",
                "telemetry_source",
                "operation",
                "resource",
            ],
            "aiguard_evidence_candidates": [
                "runtime_queue_overload",
                "runtime_thermal_instability",
            ],
        },
        "downstream_guard_alignment": {
            "declared_by": "orchestrator",
            "producer_lineage_evidence_type": (
                ORCHESTRATOR_PRODUCER_LINEAGE_AIGUARD_EVIDENCE_TYPE
            ),
            "operation_evidence_candidates": [
                *ORCHESTRATOR_EDGEENV_AIGUARD_EVIDENCE_CANDIDATES
            ],
            "validated_by": [
                "edgeenv runs telemetry inspect-history",
                "inferedge-aiguard reason-edgeenv-regression",
                "inferedgelab runtime-intelligence bundle manifest gate",
            ],
            "orchestrator_is_final_decision_owner": False,
            "lab_is_final_decision_owner": True,
        },
    }


def _operation_risk_rollup_payload() -> dict:
    return {
        "schema_version": "inferedge-orchestrator-operation-risk-rollup-v1",
        "operation_context_role": "supplemental",
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
        "not_a_deployment_decision": True,
        "risk_level": "review",
        "first_read": "review_operation_risk_context",
        "primary_reasons": [
            "queue_pressure_overloaded",
            "scheduler_delay_present",
            "fallback_used",
        ],
        "affected_tasks": {
            "deadline_missed": ["vision_agent"],
            "fallback": ["voice_command_agent"],
            "scheduler_delay": ["vision_agent"],
            "degraded": ["vision_agent"],
            "constrained": [],
        },
        "queue_pressure_state": "overloaded",
        "queue_pressure_reason": "queue_backlog_threshold_exceeded",
        "max_total_queue_depth": 7,
        "deadline_missed_count": 2,
        "fallback_count": 1,
        "drop_count": 1,
        "scheduler_delay_event_count": 1,
        "policy_decision_count": 2,
    }


def _operation_timeline_summary_payload() -> dict:
    return {
        "schema_version": "inferedge-orchestrator-operation-timeline-summary-v1",
        "source": (
            "queue_depth_timeline+latency_timeline+policy_decision_log+"
            "runtime_event_summary"
        ),
        "sample_counts": {
            "queue_depth": 2,
            "latency": 2,
            "policy_decision": 2,
            "runtime_event": 3,
        },
        "queue": {
            "max_total_queue_depth": 7,
            "average_total_queue_depth": 4.5,
            "overload_backlog_threshold": 5,
            "pressure_state": "overloaded",
            "pressure_reason": "queue_backlog_threshold_exceeded",
            "max_pressure_task": "vision_agent",
            "max_queue_depth_by_task": {"vision_agent": 7},
        },
        "latency": {
            "sample_count": 2,
            "max_latency_ms": 50.0,
            "max_queue_wait_ms": 15.0,
            "max_queue_wait_ms_by_task": {"vision_agent": 15.0},
            "tasks_with_deadline_miss": ["vision_agent"],
        },
        "policy": {
            "decision_count": 2,
            "decision_reasons": ["queue_backlog_threshold_exceeded"],
            "first_decision": {
                "decision_reason": "queue_backlog_threshold_exceeded",
            },
            "latest_decision": {
                "decision_reason": "queue_backlog_threshold_exceeded",
            },
        },
        "policy_pressure": _policy_pressure_summary_payload(),
        "stale_drop": _stale_drop_summary_payload(),
        "affected_tasks": {
            "deadline_missed": ["vision_agent"],
            "fallback": ["voice_command_agent"],
            "scheduler_delay": ["vision_agent"],
            "degraded": ["vision_agent"],
            "constrained": [],
            "stale_drop": ["vision_agent"],
            "policy_pressure": ["vision_agent", "voice_command_agent"],
        },
        "review_hints": [
            "review_queue_pressure",
            "review_scheduler_delay",
            "review_deadline_miss",
            "review_fallback_use",
            "review_stale_drop",
            "review_policy_pressure",
        ],
    }


def _policy_pressure_summary_payload() -> dict:
    return {
        "schema_version": "inferedge-orchestrator-policy-pressure-summary-v1",
        "role": "supplemental",
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
        "not_a_deployment_decision": True,
        "first_read": "review_policy_pressure_context",
        "decision_count": 2,
        "decision_reason_counts": {
            "queue_backlog_threshold_exceeded": 2,
        },
        "limited_tasks": ["vision_agent", "voice_command_agent"],
        "protected_tasks": ["safety_monitor_agent"],
        "fallback_tasks": ["voice_command_agent"],
        "fallback_decision_count": 1,
        "backlog_thresholds": [3],
        "max_total_backlog_before": 7,
        "max_backlog_over_threshold": 4,
        "pressure_markers": [
            "policy_decision_present",
            "backlog_exceeded_threshold",
            "fallback_policy_used",
            "workload_limited_by_policy",
            "scheduler_delay_present",
        ],
        "interpretation": (
            "Scheduler policy pressure preserved as Lab review context only."
        ),
    }


def _stale_drop_summary_payload() -> dict:
    return {
        "schema_version": "inferedge-orchestrator-stale-drop-summary-v1",
        "operation_context_role": "supplemental",
        "scheduler_owner": "orchestrator",
        "decision_owner": "lab",
        "not_a_deployment_decision": True,
        "first_read": "review_stale_drop_context",
        "stale_drop_count": 1,
        "total_drop_count": 1,
        "stale_drop_rate": 1.0,
        "stale_drop_reasons": {
            "stale_frame_expired": 1,
        },
        "stale_drop_reason_classes": ["stale_frame"],
        "tasks_with_stale_drop": ["vision_agent"],
        "task_counts": {"vision_agent": 1},
    }


def _runtime_history_seed(run_id: str, *, sequence_id: int) -> dict:
    return {
        "schema_version": "inferedge-runtime-telemetry-history-seed-v1",
        "evidence_role": "runtime_telemetry_history_seed",
        "registry_owner": "edgeenv",
        "decision_owner": "lab",
        "source_result_schema_version": "inferedge-runtime-result-v1",
        "source_telemetry_schema_version": "inferedge-runtime-telemetry-v1",
        "replay_scope": "single_result_to_history",
        "replay_ready": True,
        "production_monitoring": False,
        "missing_telemetry_is_failure": False,
        "source_result": {
            "run_id": run_id,
            "compare_key": "yolov8n__b1__h640w640__fp32",
            "backend_key": "onnxruntime__cpu",
            "engine_backend": "onnxruntime",
            "device": "cpu",
            "precision": "fp32",
            "power_mode": "unknown",
        },
        "run_config": {
            "batch": 1,
            "height": 640,
            "width": 640,
            "warmup": 1,
            "runs": 10,
            "timeout_ms": None,
            "input_mode": "dummy",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown",
        },
        "points": [
            {
                "execution_sequence_id": sequence_id,
                "telemetry_timestamp": f"2026-05-21T00:00:0{sequence_id}Z",
                "mean_ms": 100.0 + sequence_id,
                "p99_ms": 130.0 + sequence_id,
                "timeout_observed": False,
            }
        ],
    }
