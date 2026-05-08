#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/smoke_jetson_sampled_bundle_handoff.sh [options]

Run Jetson sampled evidence bundle handoff smoke for same-condition,
runtime-conditional, and target-conditional compare paths.

Options:
  --python PATH        Python interpreter to use (default: EDGEENV_JETSON_PYTHON or python3)
  --edgeenv-root PATH  Source successful-run registry root (default: temp dir)
  --import-root PATH   Imported successful-run registry root (default: temp dir)
  --bundle-dir PATH    Exported zip bundle directory (default: temp dir)
  --bundle-summary-output PATH
                       Optional Markdown path for report bundle-summary smoke
  --bundle-summary-source-device NAME
                       Source device label for bundle-summary output (default: hostname)
  --keep-artifacts     Keep temp artifacts after the script exits
  -h, --help           Show this help

This script uses PYTHONPATH instead of editable install. It creates sampled
Jetson runs, exports every run as an evidence zip, imports the bundles into a
fresh registry root, and verifies compare output still follows protocol-first
rules after handoff. If --bundle-summary-output is set, it also generates and
validates a read-only Markdown bundle-summary from the imported registry.
EOF
}

python_bin="${EDGEENV_JETSON_PYTHON:-python3}"
edgeenv_root=""
import_root=""
bundle_dir=""
bundle_summary_output=""
bundle_summary_source_device="$(hostname 2>/dev/null || printf 'jetson')"
keep_artifacts=0
edgeenv_root_is_temp=0
import_root_is_temp=0
bundle_dir_is_temp=0
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
    --import-root)
      require_value "$@"
      import_root="$2"
      shift 2
      ;;
    --bundle-dir)
      require_value "$@"
      bundle_dir="$2"
      shift 2
      ;;
    --bundle-summary-output)
      require_value "$@"
      bundle_summary_output="$2"
      shift 2
      ;;
    --bundle-summary-source-device)
      require_value "$@"
      bundle_summary_source_device="$2"
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
  edgeenv_root="$(mktemp -d /tmp/InferEdgeEnv-jetson-bundle-source.XXXXXX)/.edgeenv"
  edgeenv_root_is_temp=1
fi
if [[ -z "$import_root" ]]; then
  import_root="$(mktemp -d /tmp/InferEdgeEnv-jetson-bundle-import.XXXXXX)/.edgeenv"
  import_root_is_temp=1
fi
if [[ -z "$bundle_dir" ]]; then
  bundle_dir="$(mktemp -d /tmp/InferEdgeEnv-jetson-bundles.XXXXXX)"
  bundle_dir_is_temp=1
fi

cleanup() {
  if [[ "$keep_artifacts" -eq 0 ]]; then
    if [[ "$edgeenv_root_is_temp" -eq 1 ]]; then
      rm -rf "$(dirname "$edgeenv_root")"
    fi
    if [[ "$import_root_is_temp" -eq 1 ]]; then
      rm -rf "$(dirname "$import_root")"
    fi
    if [[ "$bundle_dir_is_temp" -eq 1 ]]; then
      rm -rf "$bundle_dir"
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

latest_run_id() {
  find "${edgeenv_root}/runs" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort | tail -n 1
}

run_sampled() {
  local target_profile="$1"
  local bench_config="$2"
  run_cli bench run \
    --target "$target_profile" \
    --config "$bench_config" \
    --edgeenv-root "$edgeenv_root" >&2
  latest_run_id
}

assert_compare() {
  local label="$1"
  local run_id_a="$2"
  local run_id_b="$3"
  local comparable="$4"
  local mode="$5"
  local required_reason="$6"
  local expect_delta="$7"
  local output

  output="$(run_cli report compare "$run_id_a" "$run_id_b" --edgeenv-root "$import_root")"
  printf '%s\n' "$output"

  if ! grep -q "Comparable: ${comparable}" <<<"$output"; then
    echo "${label}: expected Comparable: ${comparable}" >&2
    exit 1
  fi
  if ! grep -q "Mode: ${mode}" <<<"$output"; then
    echo "${label}: expected Mode: ${mode}" >&2
    exit 1
  fi
  if ! grep -q "$required_reason" <<<"$output"; then
    echo "${label}: expected reason containing ${required_reason}" >&2
    exit 1
  fi
  if [[ "$expect_delta" == "yes" ]]; then
    if ! grep -q "Metrics Delta:" <<<"$output"; then
      echo "${label}: expected Metrics Delta after imported same-condition compare" >&2
      exit 1
    fi
  else
    if grep -q "Metrics Delta:" <<<"$output"; then
      echo "${label}: conditional compare must suppress Metrics Delta" >&2
      exit 1
    fi
  fi
  if grep -qi "resource" <<<"$output" || grep -qi "sampler" <<<"$output"; then
    echo "${label}: compare output should not use resource/sampler evidence as a compare gate" >&2
    exit 1
  fi
}

echo "EdgeEnv Jetson sampled evidence bundle handoff smoke"
echo "repo_root=$repo_root"
echo "python=$python_bin"
echo "edgeenv_root=$edgeenv_root"
echo "import_root=$import_root"
echo "bundle_dir=$bundle_dir"

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
        "Missing runtime dependencies for Jetson sampled bundle handoff smoke:",
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
if [[ "$import_root_is_temp" -eq 0 && -e "$import_root" ]]; then
  echo "Custom --import-root already exists; choose an empty path: $import_root" >&2
  exit 1
fi
if [[ "$bundle_dir_is_temp" -eq 0 && -e "$bundle_dir" ]]; then
  echo "Custom --bundle-dir already exists; choose an empty path: $bundle_dir" >&2
  exit 1
fi
mkdir -p "$(dirname "$edgeenv_root")" "$(dirname "$import_root")" "$bundle_dir"

base_config="${repo_root}/examples/benches/jetson_sampled_local.yaml"
base_profile="${repo_root}/examples/profiles/jetson_nano_sampled_local.yaml"
variant_dir="$(mktemp -d /tmp/InferEdgeEnv-jetson-bundle-variants.XXXXXX)"
provider_config="${variant_dir}/jetson_sampled_provider_variant.yaml"
target_profile="${variant_dir}/jetson_nano_sampled_target_variant.yaml"

"$python_bin" - "$base_config" "$provider_config" "$base_profile" "$target_profile" <<'PY'
import sys
from pathlib import Path

import yaml

base_config = Path(sys.argv[1])
provider_config = Path(sys.argv[2])
base_profile = Path(sys.argv[3])
target_profile = Path(sys.argv[4])

provider_payload = yaml.safe_load(base_config.read_text(encoding="utf-8"))
provider_payload["name"] = "jetson-sampled-local-provider-variant"
provider_payload["execution_provider"] = "jetson-cpu-demo-variant"
provider_config.write_text(
    yaml.safe_dump(provider_payload, sort_keys=False),
    encoding="utf-8",
)

target_payload = yaml.safe_load(base_profile.read_text(encoding="utf-8"))
target_payload["target_name"] = "jetson-nano-sampled-local-target-variant"
target_payload["runtime_tags"] = [*target_payload.get("runtime_tags", []), "target-variant"]
target_profile.write_text(
    yaml.safe_dump(target_payload, sort_keys=False),
    encoding="utf-8",
)
PY

run_cli doctor
run_cli profile validate "$base_profile"
run_cli profile validate "$target_profile"
run_cli bench validate "$base_config"
run_cli bench validate "$provider_config"

same_a="$(run_sampled "$base_profile" "$base_config")"
same_b="$(run_sampled "$base_profile" "$base_config")"
runtime_a="$(run_sampled "$base_profile" "$base_config")"
runtime_b="$(run_sampled "$base_profile" "$provider_config")"
target_a="$(run_sampled "$base_profile" "$base_config")"
target_b="$(run_sampled "$target_profile" "$base_config")"

run_ids=("$same_a" "$same_b" "$runtime_a" "$runtime_b" "$target_a" "$target_b")
unique_count="$(printf '%s\n' "${run_ids[@]}" | sort -u | wc -l | tr -d ' ')"
if [[ "$unique_count" != "6" ]]; then
  echo "Expected six unique run ids, got ${unique_count}: ${run_ids[*]}" >&2
  exit 1
fi

for run_id in "${run_ids[@]}"; do
  run_cli runs sampler show "$run_id" --edgeenv-root "$edgeenv_root"
  archive_path="${bundle_dir}/edgeenv-run-${run_id}.zip"
  run_cli runs export "$run_id" --output "$archive_path" --edgeenv-root "$edgeenv_root"
  run_cli runs import "$archive_path" --edgeenv-root "$import_root"
  run_cli runs sampler show "$run_id" --edgeenv-root "$import_root"
done

"$python_bin" - "$edgeenv_root" "$import_root" "$bundle_dir" "${run_ids[@]}" <<'PY'
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath

source_root = Path(sys.argv[1])
import_root = Path(sys.argv[2])
bundle_dir = Path(sys.argv[3])
run_ids = sys.argv[4:]
required = {
    "result.json",
    "config.yaml",
    "target.yaml",
    "env.json",
    "stdout.log",
    "stderr.log",
}
summary = {}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


for run_id in run_ids:
    archive_path = bundle_dir / f"edgeenv-run-{run_id}.zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        top_levels = {PurePosixPath(name).parts[0] for name in names if name}
        if top_levels != {run_id}:
            raise SystemExit(f"{run_id}: archive top-level mismatch: {top_levels}")
        if any(Path(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names):
            raise SystemExit(f"{run_id}: unsafe archive path")
        if any(name.endswith("runs.db") for name in names):
            raise SystemExit(f"{run_id}: runs.db must not be exported")

        manifest = json.loads(archive.read(f"{run_id}/manifest.json"))
        if manifest.get("bundle_type") != "successful-run":
            raise SystemExit(f"{run_id}: expected successful-run bundle")
        if manifest.get("run_id") != run_id:
            raise SystemExit(f"{run_id}: manifest run_id mismatch")
        file_entries = {entry["path"]: entry for entry in manifest.get("files", [])}
        if not required.issubset(file_entries):
            missing = sorted(required - set(file_entries))
            raise SystemExit(f"{run_id}: missing required manifest entries {missing}")
        if "sampler/metadata.json" not in file_entries:
            raise SystemExit(f"{run_id}: missing sampler metadata manifest entry")

        for relative_path, entry in file_entries.items():
            archive_name = f"{run_id}/{relative_path}"
            payload = archive.read(archive_name)
            if sha256_bytes(payload) != entry.get("sha256"):
                raise SystemExit(f"{run_id}: checksum mismatch for {relative_path}")
            if len(payload) != entry.get("bytes"):
                raise SystemExit(f"{run_id}: byte-size mismatch for {relative_path}")

        metadata = json.loads(archive.read(f"{run_id}/sampler/metadata.json"))
        raw_artifacts = metadata.get("raw_artifacts", [])
        if metadata.get("sample_count", 0) < 1:
            raise SystemExit(f"{run_id}: expected at least one sampler sample")
        for raw_artifact in raw_artifacts:
            if raw_artifact not in file_entries:
                raise SystemExit(f"{run_id}: raw sampler artifact missing from manifest")
            if f"{run_id}/{raw_artifact}" not in names:
                raise SystemExit(f"{run_id}: raw sampler artifact missing from zip")

    imported_run_dir = import_root / "runs" / run_id
    source_result = json.loads(
        (source_root / "runs" / run_id / "result.json").read_text(encoding="utf-8")
    )
    imported_result = json.loads(
        (imported_run_dir / "result.json").read_text(encoding="utf-8")
    )
    imported_metadata = json.loads(
        (imported_run_dir / "sampler" / "metadata.json").read_text(encoding="utf-8")
    )
    if source_result != imported_result:
        raise SystemExit(f"{run_id}: imported result.json changed")
    for raw_artifact in imported_metadata.get("raw_artifacts", []):
        if not (imported_run_dir / raw_artifact).is_file():
            raise SystemExit(f"{run_id}: imported raw sampler artifact missing")
    summary[run_id] = {
        "archive": str(archive_path),
        "bundle_type": "successful-run",
        "manifest_files": sorted(file_entries),
        "sample_count": imported_metadata.get("sample_count"),
        "raw_artifacts": imported_metadata.get("raw_artifacts"),
        "resource_metrics_source": imported_result.get("resource_metrics", {}).get("source"),
        "runtime": imported_result.get("runtime"),
        "target_name": imported_result.get("target", {}).get("target_name"),
    }

print("JETSON_SAMPLED_BUNDLE_HANDOFF_SUMMARY=" + json.dumps(summary, sort_keys=True))
PY

assert_compare "same-condition imported bundle compare" \
  "$same_a" "$same_b" "Yes" "same-condition" "Same benchmark protocol" "yes"
assert_compare "runtime-conditional imported bundle compare" \
  "$runtime_a" "$runtime_b" "Conditional" "runtime-comparison" \
  "Different runtime or execution provider" "no"
assert_compare "target-conditional imported bundle compare" \
  "$target_a" "$target_b" "Conditional" "target-comparison" "Different target" "no"

if [[ -n "$bundle_summary_output" ]]; then
  mkdir -p "$(dirname "$bundle_summary_output")"
  run_cli report bundle-summary \
    --scenario "same-condition:${same_a}:${same_b}" \
    --scenario "runtime-conditional:${runtime_a}:${runtime_b}" \
    --scenario "target-conditional:${target_a}:${target_b}" \
    --source-device "$bundle_summary_source_device" \
    --edgeenv-root "$import_root" \
    --output "$bundle_summary_output"

  if [[ ! -s "$bundle_summary_output" ]]; then
    echo "bundle-summary output was not created: $bundle_summary_output" >&2
    exit 1
  fi
  if ! grep -q "| same-condition | ${same_a} | ${same_b} |" "$bundle_summary_output"; then
    echo "bundle-summary missing same-condition row" >&2
    exit 1
  fi
  if ! grep -q "| runtime-conditional | Conditional | runtime-comparison | absent | yes |" "$bundle_summary_output"; then
    echo "bundle-summary missing runtime-conditional imported compare row" >&2
    exit 1
  fi
  if ! grep -q "| target-conditional | Conditional | target-comparison | absent | yes |" "$bundle_summary_output"; then
    echo "bundle-summary missing target-conditional imported compare row" >&2
    exit 1
  fi
  if grep -Eqi "composite score:|^\|[[:space:]]*rank[[:space:]]*\|" "$bundle_summary_output"; then
    echo "bundle-summary output must not include ranking tables or composite score fields" >&2
    exit 1
  fi
  echo "bundle_summary_output=$bundle_summary_output"
fi

echo "Jetson sampled evidence bundle handoff smoke passed"
