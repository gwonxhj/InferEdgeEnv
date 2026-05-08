#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/smoke_jetson_source_env.sh [options]

Run the Jetson source-snapshot sampler smoke from the repository root.

Options:
  --python PATH        Python interpreter to use (default: EDGEENV_JETSON_PYTHON or python3)
  --edgeenv-root PATH  Successful-run registry root (default: temp dir)
  --import-root PATH   Import verification registry root (default: temp dir)
  --keep-artifacts     Keep temp artifacts after the script exits
  -h, --help           Show this help

This script intentionally uses PYTHONPATH instead of editable install so it can
validate a copied source snapshot inside an existing Jetson conda environment.
EOF
}

python_bin="${EDGEENV_JETSON_PYTHON:-python3}"
edgeenv_root=""
import_root=""
keep_artifacts=0
edgeenv_root_is_temp=0
import_root_is_temp=0

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
    --import-root)
      require_value "$@"
      import_root="$2"
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
  edgeenv_root="$(mktemp -d /tmp/InferEdgeEnv-jetson-source-smoke.XXXXXX)/.edgeenv"
  edgeenv_root_is_temp=1
fi
if [[ -z "$import_root" ]]; then
  import_root="$(mktemp -d /tmp/InferEdgeEnv-jetson-source-import.XXXXXX)/.edgeenv"
  import_root_is_temp=1
fi

cleanup() {
  if [[ "$keep_artifacts" -eq 0 ]]; then
    if [[ "$edgeenv_root_is_temp" -eq 1 ]]; then
      rm -rf "$(dirname "$edgeenv_root")"
    fi
    if [[ "$import_root_is_temp" -eq 1 ]]; then
      rm -rf "$(dirname "$import_root")"
    fi
  fi
}
trap cleanup EXIT

run_cli() {
  "$python_bin" -m inferedge_env.cli "$@"
}

echo "EdgeEnv Jetson source env smoke"
echo "repo_root=$repo_root"
echo "python=$python_bin"
echo "edgeenv_root=$edgeenv_root"
echo "import_root=$import_root"

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
    print("Missing runtime dependencies for Jetson source smoke:", file=sys.stderr)
    for item in missing:
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(1)
PY

if ! command -v tegrastats >/dev/null; then
  echo "tegrastats not found; this smoke requires real Jetson sampler evidence" >&2
  exit 1
fi

run_cli doctor
if command -v edgeenv >/dev/null; then
  edgeenv doctor
else
  echo "edgeenv console script not found; python -m entrypoint was validated"
fi
run_cli profile validate "${repo_root}/examples/profiles/jetson_nano_sampled_local.yaml"
run_cli bench validate "${repo_root}/examples/benches/jetson_sampled_local.yaml"

if [[ "$edgeenv_root_is_temp" -eq 0 && -e "$edgeenv_root" ]]; then
  echo "Custom --edgeenv-root already exists; choose an empty path: $edgeenv_root" >&2
  exit 1
fi
if [[ "$import_root_is_temp" -eq 0 && -e "$import_root" ]]; then
  echo "Custom --import-root already exists; choose an empty path: $import_root" >&2
  exit 1
fi
mkdir -p "$(dirname "$edgeenv_root")" "$(dirname "$import_root")"

run_cli bench run \
  --target "${repo_root}/examples/profiles/jetson_nano_sampled_local.yaml" \
  --config "${repo_root}/examples/benches/jetson_sampled_local.yaml" \
  --edgeenv-root "$edgeenv_root"

run_id="$(find "${edgeenv_root}/runs" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | tail -n 1)"
if [[ -z "$run_id" ]]; then
  echo "No successful run artifact was created" >&2
  exit 1
fi

archive_path="$(dirname "$edgeenv_root")/${run_id}.zip"
run_cli runs show "$run_id" --edgeenv-root "$edgeenv_root"
run_cli runs sampler show "$run_id" --edgeenv-root "$edgeenv_root"
run_cli runs export "$run_id" --output "$archive_path" --edgeenv-root "$edgeenv_root"
run_cli runs import "$archive_path" --edgeenv-root "$import_root"
run_cli runs sampler show "$run_id" --edgeenv-root "$import_root"

"$python_bin" - "$edgeenv_root" "$run_id" <<'PY'
import json
import sys
from pathlib import Path

edgeenv_root = Path(sys.argv[1])
run_id = sys.argv[2]
run_dir = edgeenv_root / "runs" / run_id
result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
metadata = json.loads((run_dir / "sampler" / "metadata.json").read_text(encoding="utf-8"))

if result.get("resource_metrics", {}).get("source") != "jetson-tegrastats":
    raise SystemExit("Expected jetson-tegrastats resource metrics")
if metadata.get("sample_count", 0) < 1:
    raise SystemExit("Expected at least one tegrastats sample")
for raw_artifact in metadata.get("raw_artifacts", []):
    if not (run_dir / raw_artifact).is_file():
        raise SystemExit(f"Missing raw sampler artifact: {raw_artifact}")

print(
    "JETSON_SOURCE_SMOKE_SUMMARY="
    + json.dumps(
        {
            "run_id": run_id,
            "sample_count": metadata.get("sample_count"),
            "raw_artifacts": metadata.get("raw_artifacts"),
            "resource_metrics": result.get("resource_metrics"),
        },
        sort_keys=True,
    )
)
PY

echo "Jetson source env smoke passed"
