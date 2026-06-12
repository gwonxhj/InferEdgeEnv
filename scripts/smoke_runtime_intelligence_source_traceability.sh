#!/usr/bin/env bash
set -euo pipefail

EDGEENV_DIR="${EDGEENV_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-$EDGEENV_DIR/reports/runtime_intelligence_source_traceability}"
LAB_DIR="${LAB_DIR:-$EDGEENV_DIR/../InferEdgeLab}"
LAB_SOURCE_TRACEABILITY_GATE="${LAB_SOURCE_TRACEABILITY_GATE:-$LAB_DIR/scripts/check_runtime_intelligence_source_traceability.py}"
AIGUARD_ALIGNMENT="${AIGUARD_ALIGNMENT:-$LAB_DIR/examples/runtime_intelligence_chain/aiguard_edgeenv_handoff_alignment_optional_present.json}"

usage() {
  cat <<'EOF'
InferEdgeEnv Runtime Intelligence source traceability smoke

Usage:
  bash scripts/smoke_runtime_intelligence_source_traceability.sh [--output-dir <path>] [--lab-dir <path>] [--aiguard-alignment <path>]
  bash scripts/smoke_runtime_intelligence_source_traceability.sh --help

This smoke verifies that EdgeEnv's producer-side Runtime Intelligence handoff
preserves the read-only optional AIGuard source artifact and reproduction
command. When a sibling InferEdgeLab checkout is available, it also runs Lab's
source traceability gate against the generated EdgeEnv handoff manifest.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --output-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --output-dir" >&2
        exit 2
      fi
      OUTPUT_DIR="$2"
      shift
      ;;
    --lab-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --lab-dir" >&2
        exit 2
      fi
      LAB_DIR="$2"
      LAB_SOURCE_TRACEABILITY_GATE="$LAB_DIR/scripts/check_runtime_intelligence_source_traceability.py"
      AIGUARD_ALIGNMENT="$LAB_DIR/examples/runtime_intelligence_chain/aiguard_edgeenv_handoff_alignment_optional_present.json"
      shift
      ;;
    --aiguard-alignment)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --aiguard-alignment" >&2
        exit 2
      fi
      AIGUARD_ALIGNMENT="$2"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "$EDGEENV_DIR"
mkdir -p "$OUTPUT_DIR"

PYTHON_CMD=(python)
BASELINE_RESULT="$OUTPUT_DIR/baseline_result.json"
CANDIDATE_RESULT="$OUTPUT_DIR/candidate_result.json"
REGRESSION_JSON="$OUTPUT_DIR/edgeenv_runtime_regression_with_source_traceability.json"
HISTORY_JSON="$OUTPUT_DIR/runtime_telemetry_history_with_source_traceability.json"
HANDOFF_JSON="$OUTPUT_DIR/edgeenv_runtime_intelligence_lab_handoff_source_traceability.json"
SUMMARY_MD="$OUTPUT_DIR/edgeenv_runtime_intelligence_source_traceability_smoke_summary.md"
LAB_SUMMARY_MD="$OUTPUT_DIR/lab_source_traceability_summary.md"

echo "== EdgeEnv Runtime Intelligence source traceability smoke =="
echo "Output: $OUTPUT_DIR"

"${PYTHON_CMD[@]}" - "$BASELINE_RESULT" "$CANDIDATE_RESULT" "$REGRESSION_JSON" "$HISTORY_JSON" <<'PY'
import json
import sys
from pathlib import Path

baseline_path, candidate_path, regression_path, history_path = map(Path, sys.argv[1:])


def runtime_history_seed(run_id: str, sequence_id: int) -> dict:
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


history = {
    "schema_version": "edgeenv.runtime-telemetry-history.v1",
    "summary": {
        "registered_runs": 2,
        "telemetry_runs": 2,
        "missing_telemetry_runs": 0,
        "history_seed_runs": 2,
        "history_seed_run_config_runs": 2,
    },
    "runs": [
        {
            "run_id": "baseline",
            "runtime_telemetry_history_seed": runtime_history_seed("baseline", 1),
        },
        {
            "run_id": "candidate",
            "runtime_telemetry_history_seed": runtime_history_seed("candidate", 2),
        },
    ],
    "missing_telemetry": [],
}
regression = {
    "baseline_run_id": "baseline",
    "candidate_run_id": "candidate",
    "comparable": True,
    "mode": "same-condition",
    "regression_detected": True,
    "regression_type": "mixed",
    "severity": "high",
    "runtime_telemetry_context": {
        "history": history,
        "baseline": {"run_id": "baseline"},
        "candidate": {"run_id": "candidate"},
    },
}

baseline_path.write_text(json.dumps({"run_id": "baseline"}) + "\n", encoding="utf-8")
candidate_path.write_text(json.dumps({"run_id": "candidate"}) + "\n", encoding="utf-8")
regression_path.write_text(json.dumps(regression, indent=2) + "\n", encoding="utf-8")
history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
PY

"${PYTHON_CMD[@]}" -m inferedge_env.cli report runtime-intelligence-handoff \
  --baseline-result "$BASELINE_RESULT" \
  --candidate-result "$CANDIDATE_RESULT" \
  --edgeenv-regression-report "$REGRESSION_JSON" \
  --telemetry-history "$HISTORY_JSON" \
  --output "$HANDOFF_JSON" >/dev/null

"${PYTHON_CMD[@]}" - "$HANDOFF_JSON" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
alignment = payload.get("lab_bundle_alignment", {})
traceability = alignment.get("optional_aiguard_source_traceability")
expected_command = [
    "python",
    "-m",
    "inferedge_aiguard.cli",
    "build-runtime-intelligence-optional-stale-drop",
    "--edgeenv-regression",
    "examples/runtime_intelligence/edgeenv_runtime_regression_with_optional_stale_drop_context.json",
    "--remote-dispatch",
    "examples/runtime_intelligence/remote_dispatch_fallback_recovered_result.json",
    "--orchestration-summary",
    "examples/runtime_intelligence/orchestrator_multi_workload_sustained_summary.json",
    "--save-json",
    "examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json",
]
expected_source = {
    "repository": "InferEdgeAIGuard",
    "path": "examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json",
    "schema_version": "inferedge-aiguard-diagnosis-v1",
    "role": "aiguard-optional-stale-drop-full-evidence-source",
    "context_role": "read_only_cross_repo_traceability",
    "reproduction_command": expected_command,
}

if payload.get("schema_version") != "edgeenv.runtime-intelligence-lab-handoff.v1":
    raise SystemExit("unexpected handoff schema_version")
if "guard_analysis" in payload:
    raise SystemExit("EdgeEnv handoff must not include guard_analysis")
if not isinstance(traceability, dict):
    raise SystemExit("optional_aiguard_source_traceability is missing")
if traceability.get("context_role") != "read_only_optional_source_traceability":
    raise SystemExit("optional source traceability context_role drifted")
if traceability.get("edgeenv_does_not_generate_guard_analysis") is not True:
    raise SystemExit("EdgeEnv must not claim to generate guard_analysis")
if traceability.get("lab_is_final_decision_owner") is not True:
    raise SystemExit("Lab must remain the final decision owner")
if traceability.get("optional_present_source_artifact") != expected_source:
    raise SystemExit("optional-present source artifact drifted")
if "aiguard_guard_analysis" not in alignment.get("external_file_keys", []):
    raise SystemExit("AIGuard guard_analysis must remain external")
if "aiguard_guard_analysis" in alignment.get("edgeenv_produced_file_keys", []):
    raise SystemExit("EdgeEnv-produced keys must not include AIGuard guard_analysis")
PY

LAB_GATE_STATUS="skipped"
if [[ -f "$LAB_SOURCE_TRACEABILITY_GATE" && -f "$AIGUARD_ALIGNMENT" ]]; then
  "${PYTHON_CMD[@]}" "$LAB_SOURCE_TRACEABILITY_GATE" \
    --edgeenv-handoff "$HANDOFF_JSON" \
    --aiguard-alignment "$AIGUARD_ALIGNMENT" \
    --summary-out "$LAB_SUMMARY_MD"
  LAB_GATE_STATUS="passed"
fi

cat > "$SUMMARY_MD" <<EOF
# EdgeEnv Runtime Intelligence Source Traceability Smoke

- Status: passed
- handoff_schema_version: edgeenv.runtime-intelligence-lab-handoff.v1
- optional_aiguard_source_traceability: preserved
- optional_present_source_artifact: InferEdgeAIGuard/examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json
- optional_present_reproduction_command: python -m inferedge_aiguard.cli build-runtime-intelligence-optional-stale-drop --edgeenv-regression examples/runtime_intelligence/edgeenv_runtime_regression_with_optional_stale_drop_context.json --remote-dispatch examples/runtime_intelligence/remote_dispatch_fallback_recovered_result.json --orchestration-summary examples/runtime_intelligence/orchestrator_multi_workload_sustained_summary.json --save-json examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json
- lab_source_traceability_gate: $LAB_GATE_STATUS
- ownership: edgeenv_does_not_generate_guard_analysis=true, lab_is_final_decision_owner=true
EOF

echo "EdgeEnv Runtime Intelligence source traceability smoke passed."
