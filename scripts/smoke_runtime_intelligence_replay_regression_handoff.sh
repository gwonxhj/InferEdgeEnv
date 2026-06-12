#!/usr/bin/env bash
set -euo pipefail

EDGEENV_DIR="${EDGEENV_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OUTPUT_DIR="${OUTPUT_DIR:-$EDGEENV_DIR/reports/runtime_intelligence_replay_regression_handoff}"

usage() {
  cat <<'EOF'
InferEdgeEnv Runtime Intelligence replay/regression/handoff smoke

Usage:
  bash scripts/smoke_runtime_intelligence_replay_regression_handoff.sh [--python <path>] [--output-dir <path>]
  bash scripts/smoke_runtime_intelligence_replay_regression_handoff.sh --help

This smoke exercises the local-first EdgeEnv Runtime Intelligence path through
the public CLI:
  bench run with runtime telemetry
  -> runs telemetry export-history
  -> runs telemetry inspect-history
  -> report regression --telemetry-history
  -> report runtime-intelligence-handoff

It validates that telemetry history/replay and history_seed run_config context
remain supplemental evidence and that regression deltas are still gated by
same-condition comparability before Lab handoff metadata is produced.
EOF
}

python_bin="python"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      usage
      exit 0
      ;;
    --python)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --python" >&2
        exit 2
      fi
      python_bin="$2"
      shift
      ;;
    --output-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --output-dir" >&2
        exit 2
      fi
      OUTPUT_DIR="$2"
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

PYTHON_CMD=("$python_bin")
WORK_DIR="$OUTPUT_DIR/work"
EDGEENV_ROOT="$OUTPUT_DIR/.edgeenv"
EMITTER="$WORK_DIR/emit_runtime_intelligence_metrics.py"
TARGET_YAML="$WORK_DIR/local_runtime_intelligence_target.yaml"
BASELINE_CONFIG="$WORK_DIR/baseline_runtime_intelligence.yaml"
CANDIDATE_CONFIG="$WORK_DIR/candidate_runtime_intelligence.yaml"
BASELINE_LOG="$OUTPUT_DIR/baseline_bench_run.log"
CANDIDATE_LOG="$OUTPUT_DIR/candidate_bench_run.log"
EXPORT_LOG="$OUTPUT_DIR/telemetry_export_history.log"
INSPECT_LOG="$OUTPUT_DIR/telemetry_inspect_history.log"
REGRESSION_LOG="$OUTPUT_DIR/regression_report.log"
HANDOFF_LOG="$OUTPUT_DIR/runtime_intelligence_handoff.log"
HISTORY_JSON="$OUTPUT_DIR/runtime_telemetry_history.json"
REGRESSION_JSON="$OUTPUT_DIR/edgeenv_runtime_regression.json"
REGRESSION_MD="$OUTPUT_DIR/edgeenv_runtime_regression.md"
HANDOFF_JSON="$OUTPUT_DIR/edgeenv_runtime_intelligence_lab_handoff.json"
SUMMARY_MD="$OUTPUT_DIR/runtime_intelligence_replay_regression_handoff_summary.md"

echo "== EdgeEnv Runtime Intelligence replay/regression/handoff smoke =="
echo "Output: $OUTPUT_DIR"

rm -rf "$WORK_DIR" "$EDGEENV_ROOT"
mkdir -p "$WORK_DIR"

cat > "$EMITTER" <<'PY'
from __future__ import annotations

import json
import os


VARIANTS = {
    "baseline": {
        "sequence_id": 1,
        "timestamp": "2026-05-22T00:00:01Z",
        "metrics": {
            "latency_mean_ms": 100.0,
            "latency_p50_ms": 96.0,
            "latency_p95_ms": 120.0,
            "latency_p99_ms": 130.0,
            "throughput_fps": 50.0,
        },
    },
    "candidate": {
        "sequence_id": 2,
        "timestamp": "2026-05-22T00:00:02Z",
        "metrics": {
            "latency_mean_ms": 118.0,
            "latency_p50_ms": 114.0,
            "latency_p95_ms": 132.0,
            "latency_p99_ms": 171.6,
            "throughput_fps": 39.0,
        },
    },
}


def runtime_history_seed(sequence_id: int, timestamp: str) -> dict:
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
            "compare_key": "runtime-intelligence-smoke__b1__h224w224__fp32",
            "backend_key": "local-python__cpu",
            "engine_backend": "local-python",
            "device": "cpu",
            "precision": "fp32",
            "power_mode": "unknown",
        },
        "run_config": {
            "batch": 1,
            "height": 224,
            "width": 224,
            "warmup": 1,
            "runs": 3,
            "timeout_ms": None,
            "input_mode": "synthetic",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown",
        },
        "recommended_registry_key_fields": [
            "compare_key",
            "backend_key",
            "device",
            "precision",
            "power_mode",
            "run_config",
        ],
        "time_series_fields": [
            "telemetry_timestamp",
            "execution_sequence_id",
            "latency.mean_ms",
            "latency.p99_ms",
            "operation.timeout_observed",
        ],
        "points": [
            {
                "execution_sequence_id": sequence_id,
                "telemetry_timestamp": timestamp,
                "mean_ms": 100.0 + sequence_id,
                "p99_ms": 130.0 + sequence_id,
                "timeout_observed": False,
            }
        ],
    }


def runtime_telemetry(sequence_id: int, timestamp: str, metrics: dict) -> dict:
    expected_fields = ["queue_depth", "gpu_temperature", "telemetry_timestamp"]
    return {
        "schema_version": "inferedge-runtime-telemetry-v1",
        "collection_mode": "single_result_export",
        "telemetry_timestamp": timestamp,
        "execution_sequence_id": sequence_id,
        "latency": {
            "mean_ms": metrics["latency_mean_ms"],
            "p99_ms": metrics["latency_p99_ms"],
        },
        "resource": {
            "telemetry_source": "runtime-result",
            "gpu_temperature": 55.0 + sequence_id,
        },
        "operation": {
            "queue_depth": sequence_id - 1,
            "timeout_observed": False,
        },
        "coverage": {
            "schema_version": "inferedge-runtime-telemetry-coverage-v1",
            "expected_fields": expected_fields,
            "observed_fields": expected_fields,
            "missing_fields": [],
            "expected_field_count": len(expected_fields),
            "observed_field_count": len(expected_fields),
            "missing_field_count": 0,
            "coverage_ratio": 1.0,
            "comparability_owner": "edgeenv",
            "missing_telemetry_is_failure": False,
        },
        "missing_fields": [],
        "production_monitoring": False,
        "history_seed": runtime_history_seed(sequence_id, timestamp),
    }


def main() -> int:
    variant_name = os.environ.get("RUNTIME_INTELLIGENCE_VARIANT", "baseline")
    variant = VARIANTS.get(variant_name)
    if variant is None:
        valid = ", ".join(sorted(VARIANTS))
        print(f"Unknown RUNTIME_INTELLIGENCE_VARIANT={variant_name!r}; expected one of {valid}")
        return 2

    metrics = variant["metrics"]
    telemetry = runtime_telemetry(
        variant["sequence_id"],
        variant["timestamp"],
        metrics,
    )
    print(f"runtime_intelligence_variant={variant_name}")
    print("EDGEENV_METRICS_JSON=" + json.dumps(metrics, sort_keys=True))
    print("EDGEENV_RUNTIME_TELEMETRY_JSON=" + json.dumps(telemetry, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY

cat > "$TARGET_YAML" <<'EOF'
target_name: runtime-intelligence-local-smoke
target_type: local
board_name: local-dev-machine
os: local
runtime_tags:
  - local
  - runtime-intelligence-smoke
EOF

cat > "$BASELINE_CONFIG" <<EOF
name: runtime-intelligence-replay-baseline
command: python "$EMITTER"
model_name: runtime-intelligence-smoke-model
model_version: "1.0"
model_format: onnx
model_path: models/runtime-intelligence-smoke.onnx
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: true
include_postprocess: true
timeout_seconds: 30
working_directory: .
extra_env:
  RUNTIME_INTELLIGENCE_VARIANT: baseline
EOF

cat > "$CANDIDATE_CONFIG" <<EOF
name: runtime-intelligence-replay-candidate
command: python "$EMITTER"
model_name: runtime-intelligence-smoke-model
model_version: "1.0"
model_format: onnx
model_path: models/runtime-intelligence-smoke.onnx
task: object-detection
input_shape: [1, 3, 224, 224]
input_dtype: float32
runtime: local-python
execution_provider: cpu
precision: fp32
batch_size: 1
warmup_runs: 1
repeat_runs: 3
include_preprocess: true
include_postprocess: true
timeout_seconds: 30
working_directory: .
extra_env:
  RUNTIME_INTELLIGENCE_VARIANT: candidate
EOF

"${PYTHON_CMD[@]}" -m inferedge_env.cli bench run \
  --edgeenv-root "$EDGEENV_ROOT" \
  --target "$TARGET_YAML" \
  --config "$BASELINE_CONFIG" > "$BASELINE_LOG"

"${PYTHON_CMD[@]}" -m inferedge_env.cli bench run \
  --edgeenv-root "$EDGEENV_ROOT" \
  --target "$TARGET_YAML" \
  --config "$CANDIDATE_CONFIG" > "$CANDIDATE_LOG"

BASELINE_RUN_ID="$(sed -n 's/^Run ID: //p' "$BASELINE_LOG" | tail -n 1)"
CANDIDATE_RUN_ID="$(sed -n 's/^Run ID: //p' "$CANDIDATE_LOG" | tail -n 1)"
if [[ -z "$BASELINE_RUN_ID" || -z "$CANDIDATE_RUN_ID" ]]; then
  echo "Failed to parse run IDs from bench run logs" >&2
  exit 1
fi

BASELINE_RESULT="$EDGEENV_ROOT/runs/$BASELINE_RUN_ID/result.json"
CANDIDATE_RESULT="$EDGEENV_ROOT/runs/$CANDIDATE_RUN_ID/result.json"

"${PYTHON_CMD[@]}" -m inferedge_env.cli runs telemetry export-history \
  --edgeenv-root "$EDGEENV_ROOT" \
  --output "$HISTORY_JSON" > "$EXPORT_LOG"

"${PYTHON_CMD[@]}" -m inferedge_env.cli runs telemetry inspect-history \
  "$HISTORY_JSON" > "$INSPECT_LOG"

"${PYTHON_CMD[@]}" -m inferedge_env.cli report regression \
  "$BASELINE_RUN_ID" \
  "$CANDIDATE_RUN_ID" \
  --edgeenv-root "$EDGEENV_ROOT" \
  --telemetry-history "$HISTORY_JSON" \
  --output-json "$REGRESSION_JSON" \
  --output-md "$REGRESSION_MD" > "$REGRESSION_LOG"

"${PYTHON_CMD[@]}" -m inferedge_env.cli report runtime-intelligence-handoff \
  --baseline-result "$BASELINE_RESULT" \
  --candidate-result "$CANDIDATE_RESULT" \
  --edgeenv-regression-report "$REGRESSION_JSON" \
  --telemetry-history "$HISTORY_JSON" \
  --output "$HANDOFF_JSON" > "$HANDOFF_LOG"

"${PYTHON_CMD[@]}" - "$HISTORY_JSON" "$REGRESSION_JSON" "$HANDOFF_JSON" <<'PY'
import json
import sys
from pathlib import Path

history = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
regression = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
handoff = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

summary = history.get("summary", {})
if history.get("schema_version") != "edgeenv.runtime-telemetry-history.v1":
    raise SystemExit("unexpected telemetry history schema")
if summary.get("telemetry_runs") != 2:
    raise SystemExit("telemetry history must include two telemetry runs")
if summary.get("history_seed_runs") != 2:
    raise SystemExit("telemetry history must preserve two history seeds")
if summary.get("history_seed_run_config_runs") != 2:
    raise SystemExit("telemetry history must preserve two history seed run_config snapshots")
if summary.get("missing_telemetry_runs") != 0:
    raise SystemExit("telemetry history smoke should not create missing telemetry gaps")

if regression.get("mode") != "same-condition":
    raise SystemExit("regression smoke must stay same-condition")
if regression.get("regression_detected") is not True:
    raise SystemExit("regression smoke must detect the candidate regression")
triggered = {
    item.get("name")
    for item in regression.get("evidence", {}).get("triggered_thresholds", [])
    if isinstance(item, dict)
}
if "p99_latency_high" not in triggered:
    raise SystemExit("regression smoke must trigger p99 latency review evidence")
context = regression.get("runtime_telemetry_context")
if not isinstance(context, dict):
    raise SystemExit("regression smoke must attach runtime telemetry context")
if context.get("role") != "supplemental_runtime_telemetry_context":
    raise SystemExit("runtime telemetry context role drifted")
if "guard_analysis" in regression:
    raise SystemExit("EdgeEnv regression must not include guard_analysis")
if "Regression deltas are still gated by same-condition comparability." not in context.get("notes", []):
    raise SystemExit("regression smoke lost comparability-first note")
if context.get("history", {}).get("summary", {}).get("history_seed_run_config_runs") != 2:
    raise SystemExit("regression telemetry context lost history seed run_config summary")

if handoff.get("schema_version") != "edgeenv.runtime-intelligence-lab-handoff.v1":
    raise SystemExit("unexpected handoff schema")
if "guard_analysis" in handoff:
    raise SystemExit("EdgeEnv handoff must not include guard_analysis")
files = handoff.get("files", {})
if "runtime_telemetry_history" not in files:
    raise SystemExit("handoff must reference runtime telemetry history")
edgeenv_summary = handoff.get("edgeenv_report_summary", {})
if edgeenv_summary.get("history_seed_runs") != 2:
    raise SystemExit("handoff must summarize two history seed runs")
if edgeenv_summary.get("history_seed_run_config_runs") != 2:
    raise SystemExit("handoff must summarize two history seed run_config snapshots")
if not edgeenv_summary.get("history_seed_run_config_markers"):
    raise SystemExit("handoff must expose compact history seed run_config markers")
alignment = handoff.get("lab_bundle_alignment", {})
flags = alignment.get("boundary_flags", {})
if flags.get("edgeenv_does_not_generate_guard_analysis") is not True:
    raise SystemExit("handoff must keep EdgeEnv guard_analysis boundary")
if flags.get("lab_is_final_decision_owner") is not True:
    raise SystemExit("handoff must keep Lab final decision ownership")
if "aiguard_guard_analysis" not in alignment.get("external_file_keys", []):
    raise SystemExit("handoff must keep AIGuard guard_analysis external")
PY

grep -q "Runtime telemetry history valid" "$INSPECT_LOG"
grep -q "Runtime history seed run_config runs: 2" "$INSPECT_LOG"
grep -q "Scope: read-only local replay validation" "$INSPECT_LOG"
grep -q "Regression detected: true" "$REGRESSION_LOG"
grep -q "Runtime Telemetry Context:" "$REGRESSION_LOG"
grep -q "p99_latency_high" "$REGRESSION_LOG"
grep -q "role: supplemental context, not a comparability gate" "$REGRESSION_LOG"
grep -q "History seed entries: 2" "$HANDOFF_LOG"
grep -q "History seed run_config markers:" "$HANDOFF_LOG"
grep -q "Lab remains the final deployment decision owner." "$HANDOFF_LOG"

cat > "$SUMMARY_MD" <<EOF
# EdgeEnv Runtime Intelligence Replay Regression Handoff Smoke

- Status: passed
- baseline_run_id: $BASELINE_RUN_ID
- candidate_run_id: $CANDIDATE_RUN_ID
- telemetry_history_schema: edgeenv.runtime-telemetry-history.v1
- telemetry_runs: 2
- history_seed_runs: 2
- history_seed_run_config_runs: 2
- regression_mode: same-condition
- regression_detected: true
- triggered_threshold: p99_latency_high
- runtime_telemetry_context_role: supplemental_runtime_telemetry_context
- comparability_first: true
- handoff_schema_version: edgeenv.runtime-intelligence-lab-handoff.v1
- handoff_references_runtime_telemetry_history: true
- edgeenv_does_not_generate_guard_analysis: true
- lab_is_final_decision_owner: true
- production_observability_platform: false
EOF

echo "EdgeEnv Runtime Intelligence replay/regression/handoff smoke passed."
