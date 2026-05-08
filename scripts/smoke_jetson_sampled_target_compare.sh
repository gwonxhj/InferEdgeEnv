#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/smoke_jetson_sampled_target_compare.sh [options]

Run two Jetson sampled local runs with a deliberate target profile difference
and verify target-comparison output with metric deltas suppressed.

Options:
  --python PATH        Python interpreter to use (default: EDGEENV_JETSON_PYTHON or python3)
  --edgeenv-root PATH  Successful-run registry root (default: temp dir)
  --keep-artifacts     Keep temp artifacts after the script exits
  -h, --help           Show this help

This script uses PYTHONPATH instead of editable install. It keeps model identity,
runtime identity, and benchmark protocol the same, changes only target metadata
for the second run, and verifies sampled resource evidence remains outside
compare gates.
EOF
}

python_bin="${EDGEENV_JETSON_PYTHON:-python3}"
edgeenv_root=""
keep_artifacts=0
edgeenv_root_is_temp=0
variant_dir=""

require_value() {
  if [[ $# -lt 2 || "$2" == -* ]]; then
    echo "Missing value for $1" >&2
    usage >&2
    exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      require_value "$@"
      python_bin="$2"
      shift 2
      ;;
    --edgeenv-root)
      require_value "$@"
      edgeenv_root="$2"
      shift 2
      ;;
    --keep-artifacts)
      keep_artifacts=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${repo_root}${PYTHONPATH:+:${PYTHONPATH}}"
if [[ "$python_bin" == */* ]]; then
  python_dir="$(cd "$(dirname "$python_bin")" && pwd)"
  if [[ -x "${python_dir}/edgeenv" ]]; then
    export PATH="${python_dir}:${PATH}"
  fi
fi

if [[ -z "$edgeenv_root" ]]; then
  edgeenv_root="$(mktemp -d /tmp/InferEdgeEnv-jetson-sampled-target.XXXXXX)/.edgeenv"
  edgeenv_root_is_temp=1
fi

cleanup() {
  if [[ "$keep_artifacts" -eq 0 ]]; then
    if [[ "$edgeenv_root_is_temp" -eq 1 ]]; then
      rm -rf "$(dirname "$edgeenv_root")"
    fi
    if [[ -n "$variant_dir" ]]; then
      rm -rf "$variant_dir"
    fi
  fi
}
trap cleanup EXIT

run_cli() {
  "$python_bin" -m inferedge_env.cli "$@"
}

echo "EdgeEnv Jetson sampled target comparison smoke"
echo "repo_root=$repo_root"
echo "python=$python_bin"
echo "edgeenv_root=$edgeenv_root"

"$python_bin" - <<'PY'
import importlib
import sys

required = ["typer", "rich", "pydantic", "yaml"]
missing = []
for module_name in required:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        missing.append(f"{module_name}: {exc}")

if missing:
    print(
        "Missing runtime dependencies for Jetson sampled target compare smoke:",
        file=sys.stderr,
    )
    for item in missing:
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(1)
PY

if ! command -v tegrastats >/dev/null; then
  echo "tegrastats not found; this smoke requires real Jetson sampler evidence" >&2
  exit 1
fi

if [[ "$edgeenv_root_is_temp" -eq 0 && -e "$edgeenv_root" ]]; then
  echo "Custom --edgeenv-root already exists; choose an empty path: $edgeenv_root" >&2
  exit 1
fi
mkdir -p "$(dirname "$edgeenv_root")"

bench_config="${repo_root}/examples/benches/jetson_sampled_local.yaml"
base_profile="${repo_root}/examples/profiles/jetson_nano_sampled_local.yaml"
variant_dir="$(mktemp -d /tmp/InferEdgeEnv-jetson-target-profile.XXXXXX)"
variant_profile="${variant_dir}/jetson_nano_sampled_target_variant.yaml"

"$python_bin" - "$base_profile" "$variant_profile" <<'PY'
import sys
from pathlib import Path

import yaml

source = Path(sys.argv[1])
target = Path(sys.argv[2])
payload = yaml.safe_load(source.read_text(encoding="utf-8"))
payload["target_name"] = "jetson-nano-sampled-local-target-variant"
payload["runtime_tags"] = [*payload.get("runtime_tags", []), "target-variant"]
target.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
PY

run_cli doctor
run_cli profile validate "$base_profile"
run_cli profile validate "$variant_profile"
run_cli bench validate "$bench_config"

run_cli bench run \
  --target "$base_profile" \
  --config "$bench_config" \
  --edgeenv-root "$edgeenv_root"
run_cli bench run \
  --target "$variant_profile" \
  --config "$bench_config" \
  --edgeenv-root "$edgeenv_root"

mapfile -t run_ids < <(find "${edgeenv_root}/runs" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort)
if [[ "${#run_ids[@]}" -ne 2 ]]; then
  echo "Expected exactly two successful run artifacts, found ${#run_ids[@]}" >&2
  exit 1
fi

run_id_a="${run_ids[0]}"
run_id_b="${run_ids[1]}"

run_cli runs sampler show "$run_id_a" --edgeenv-root "$edgeenv_root"
run_cli runs sampler show "$run_id_b" --edgeenv-root "$edgeenv_root"
compare_output="$(run_cli report compare "$run_id_a" "$run_id_b" --edgeenv-root "$edgeenv_root")"
printf '%s\n' "$compare_output"

if ! grep -q "Comparable: Conditional" <<<"$compare_output"; then
  echo "Expected Comparable: Conditional" >&2
  exit 1
fi
if ! grep -q "Mode: target-comparison" <<<"$compare_output"; then
  echo "Expected Mode: target-comparison" >&2
  exit 1
fi
if ! grep -q "Different target" <<<"$compare_output"; then
  echo "Expected target difference reason" >&2
  exit 1
fi
if grep -q "Different runtime or execution provider" <<<"$compare_output"; then
  echo "Target comparison should not report runtime/provider difference" >&2
  exit 1
fi
if grep -q "Metrics Delta:" <<<"$compare_output"; then
  echo "Conditional target compare must suppress Metrics Delta" >&2
  exit 1
fi
if grep -qi "resource" <<<"$compare_output" || grep -qi "sampler" <<<"$compare_output"; then
  echo "Compare output should not use resource/sampler evidence as a compare gate" >&2
  exit 1
fi

"$python_bin" - "$edgeenv_root" "$run_id_a" "$run_id_b" <<'PY'
import json
import sys
from pathlib import Path

edgeenv_root = Path(sys.argv[1])
run_ids = sys.argv[2:]
summary = {}
targets = set()
runtimes = set()
for run_id in run_ids:
    run_dir = edgeenv_root / "runs" / run_id
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    metadata = json.loads((run_dir / "sampler" / "metadata.json").read_text(encoding="utf-8"))
    targets.add(json.dumps(result["target"], sort_keys=True))
    runtimes.add(json.dumps(result["runtime"], sort_keys=True))
    if result.get("resource_metrics", {}).get("source") != "jetson-tegrastats":
        raise SystemExit(f"{run_id}: expected jetson-tegrastats resource metrics")
    if metadata.get("sample_count", 0) < 1:
        raise SystemExit(f"{run_id}: expected at least one tegrastats sample")
    for raw_artifact in metadata.get("raw_artifacts", []):
        if not (run_dir / raw_artifact).is_file():
            raise SystemExit(f"{run_id}: missing raw sampler artifact {raw_artifact}")
    summary[run_id] = {
        "target_name": result["target"]["target_name"],
        "runtime": result["runtime"],
        "sample_count": metadata.get("sample_count"),
        "raw_artifacts": metadata.get("raw_artifacts"),
        "resource_metrics": result.get("resource_metrics"),
    }

if len(targets) != 2:
    raise SystemExit("Expected exactly two target identities")
if len(runtimes) != 1:
    raise SystemExit("Expected runtime identity to remain the same")

print("JETSON_SAMPLED_TARGET_SUMMARY=" + json.dumps(summary, sort_keys=True))
PY

echo "Jetson sampled target comparison smoke passed"
