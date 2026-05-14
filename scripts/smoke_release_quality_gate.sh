#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/smoke_release_quality_gate.sh [options]

Options:
  --python PATH       Python executable to use for module entrypoint and pytest.
                      Default: python
  --work-root PATH    Empty/non-existing work root for generated artifacts.
                      Default: mktemp under /private/tmp or /tmp
  --skip-pytest       Skip python -m pytest -q. Use only after pytest already passed.
  --keep-artifacts    Keep the temporary work root after the smoke passes.
  -h, --help          Show this help.

Runs the local release quality gate without requiring Jetson hardware:
doctor, whitespace check, pytest, fake/local/resource/compare/export/import,
bundle-summary, and failed-run portability smoke.
USAGE
}

python_bin="python"
work_root=""
skip_pytest=0
keep_artifacts=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      python_bin="$2"
      shift 2
      ;;
    --work-root)
      work_root="$2"
      shift 2
      ;;
    --skip-pytest)
      skip_pytest=1
      shift
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
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -z "$work_root" ]]; then
  tmp_parent="/private/tmp"
  if [[ ! -d "$tmp_parent" ]]; then
    tmp_parent="/tmp"
  fi
  work_root="$(mktemp -d "${tmp_parent}/inferedge-release-quality.XXXXXX")"
else
  if [[ -e "$work_root" ]]; then
    echo "work root already exists: $work_root" >&2
    exit 2
  fi
  mkdir -p "$work_root"
fi

cleanup() {
  if [[ "$keep_artifacts" -eq 0 && ( "$work_root" == /tmp/inferedge-release-quality.* || "$work_root" == /private/tmp/inferedge-release-quality.* ) ]]; then
    rm -rf "$work_root"
  fi
}
trap cleanup EXIT

run_cli() {
  "$python_bin" -m inferedge_env.cli "$@"
}

run_and_capture_run_id() {
  local output
  output="$("$@")"
  printf '%s\n' "$output" >&2
  printf '%s\n' "$output" | awk -F': ' '/^Run ID:/ {print $2; exit}'
}

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "expected file missing: $path" >&2
    exit 1
  fi
}

require_output_contains() {
  local output="$1"
  local expected="$2"
  if [[ "$output" != *"$expected"* ]]; then
    echo "expected output to contain: $expected" >&2
    echo "$output" >&2
    exit 1
  fi
}

echo "[release-quality] work root: $work_root"

echo "[release-quality] doctor and whitespace"
"$python_bin" -m inferedge_env.cli doctor
edgeenv doctor
git diff --check

if [[ "$skip_pytest" -eq 0 ]]; then
  echo "[release-quality] pytest"
  "$python_bin" -m pytest -q
fi

echo "[release-quality] validate representative examples"
run_cli profile validate examples/profiles/local_fake.yaml
run_cli profile validate examples/profiles/local.yaml
run_cli bench validate examples/benches/yolov8n_fire.yaml
run_cli bench validate examples/benches/local_adapter_template.yaml
run_cli bench validate examples/benches/local_resource_metrics.yaml
run_cli bench validate examples/benches/local_compare_a.yaml
run_cli bench validate examples/benches/local_compare_b.yaml
run_cli bench validate examples/benches/local_sampler_malformed_resource.yaml

edgeenv_root="${work_root}/.edgeenv"
imported_root="${work_root}/imported.edgeenv"
failed_import_root="${work_root}/imported-failed.edgeenv"
bundle_dir="${work_root}/bundles"
mkdir -p "$bundle_dir"

echo "[release-quality] fake run"
fake_run_id="$(run_and_capture_run_id run_cli bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml --edgeenv-root "$edgeenv_root")"
run_cli runs show "$fake_run_id" --edgeenv-root "$edgeenv_root" >/dev/null

echo "[release-quality] local adapter run"
adapter_run_id="$(run_and_capture_run_id run_cli bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml --edgeenv-root "$edgeenv_root")"
run_cli runs show "$adapter_run_id" --edgeenv-root "$edgeenv_root" >/dev/null

echo "[release-quality] resource query and portability"
resource_run_id="$(run_and_capture_run_id run_cli bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml --edgeenv-root "$edgeenv_root")"
resource_output="$(run_cli runs resources list --metric memory_peak_mb --json --edgeenv-root "$edgeenv_root")"
require_output_contains "$resource_output" '"memory_peak_mb"'
resource_zip="${bundle_dir}/resource-run.zip"
run_cli runs export "$resource_run_id" --output "$resource_zip" --edgeenv-root "$edgeenv_root"
require_file "$resource_zip"
run_cli runs import "$resource_zip" --edgeenv-root "$imported_root"
imported_resource_output="$(run_cli runs resources list --metric memory_peak_mb --json --edgeenv-root "$imported_root")"
require_output_contains "$imported_resource_output" "$resource_run_id"
require_output_contains "$imported_resource_output" '"example-script"'

echo "[release-quality] compare and bundle-summary"
compare_run_a="$(run_and_capture_run_id run_cli bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml --edgeenv-root "$edgeenv_root")"
compare_run_b="$(run_and_capture_run_id run_cli bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml --edgeenv-root "$edgeenv_root")"
compare_output="$(run_cli report compare "$compare_run_a" "$compare_run_b" --edgeenv-root "$edgeenv_root")"
require_output_contains "$compare_output" "Comparable: Yes"
require_output_contains "$compare_output" "Mode: same-condition"
require_output_contains "$compare_output" "Metrics Delta:"
summary_path="${work_root}/bundle-summary.md"
run_cli report bundle-summary --scenario "same-condition:${compare_run_a}:${compare_run_b}" --edgeenv-root "$edgeenv_root" --output "$summary_path"
require_file "$summary_path"
if grep -qiE '^#+[[:space:]]*(Ranking|Leaderboard)|composite_score|Composite Score:' "$summary_path"; then
  echo "bundle summary must not introduce ranking tables or composite score fields" >&2
  exit 1
fi

echo "[release-quality] failed-run portability"
set +e
failed_output="$(run_cli bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml --edgeenv-root "$edgeenv_root" 2>&1)"
failed_status=$?
set -e
printf '%s\n' "$failed_output" >&2
if [[ "$failed_status" -eq 0 ]]; then
  echo "malformed resource metrics run unexpectedly succeeded" >&2
  exit 1
fi
require_output_contains "$failed_output" "Failed run artifact:"
require_output_contains "$failed_output" "Registry: not updated"
require_output_contains "$failed_output" "Hint:"
failed_run_id="$(printf '%s\n' "$failed_output" | awk -F': ' '/^Run ID:/ {print $2; exit}')"
if [[ -z "$failed_run_id" ]]; then
  failed_run_id="$(basename "$(printf '%s\n' "$failed_output" | awk -F': ' '/^Failed run artifact:/ {print $2; exit}')")"
fi
run_cli failed-runs show "$failed_run_id" --edgeenv-root "$edgeenv_root" --log-chars 120 >/dev/null
failed_zip="${bundle_dir}/failed-run.zip"
run_cli failed-runs export "$failed_run_id" --output "$failed_zip" --edgeenv-root "$edgeenv_root"
require_file "$failed_zip"
run_cli failed-runs import "$failed_zip" --edgeenv-root "$failed_import_root"
run_cli failed-runs show "$failed_run_id" --edgeenv-root "$failed_import_root" --log-chars 0 >/dev/null
if [[ -e "${failed_import_root}/runs.db" ]]; then
  echo "failed-run import must not create runs.db" >&2
  exit 1
fi

if [[ "$keep_artifacts" -eq 1 ]]; then
  echo "[release-quality] artifacts kept: $work_root"
fi
echo "[release-quality] passed"
