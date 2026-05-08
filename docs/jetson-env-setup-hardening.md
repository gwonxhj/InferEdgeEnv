# Jetson Environment Setup Hardening

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 InferEdgeEnv source snapshot을 안정적으로 실행하기 위한 환경 준비와 smoke 절차를 정한다. 목표는 실제 장비에서 `sampler: jetson-tegrastats` sampled run을 반복 검증할 때, editable install이나 shell PATH 상태에 덜 흔들리는 진입점을 제공하는 것이다.

이 문서는 SSH target 설계가 아니다. Jetson에 이미 접속한 뒤, Jetson shell에서 local runner를 실행하는 환경 기준이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_jetson_source_env.sh` — source snapshot + existing Python environment 기반 Jetson sampled smoke
- `examples/profiles/jetson_nano_sampled_local.yaml` — optional `jetson-tegrastats` sampler profile
- `examples/benches/jetson_sampled_local.yaml` — deterministic sampled benchmark config
- `docs/jetson-sampled-run-rehearsal.md` — 실제 `nano01` sampled run 관측 기록
- `docs/packaging-entrypoints.md` — 일반 개발 환경의 editable install/entrypoint readiness 기준

기술 스택: Jetson Linux, conda Python, `PYTHONPATH`, `tegrastats`, EdgeEnv CLI

## 3. HOW — 권장 절차

### 1. Pick a Python environment

Use an environment that already has the runtime dependencies:

```bash
python - <<'PY'
import typer, rich, pydantic, yaml
print("EdgeEnv runtime dependencies: OK")
PY
```

Observed on `nano01`:

```text
/home/risenano01/miniconda3/envs/yolo_env/bin/python
Python 3.10.12
```

### 2. Confirm Jetson sampler tool

```bash
hostname
uname -a
command -v tegrastats
```

The source smoke intentionally fails if `tegrastats` is missing, because this path validates real sampler evidence rather than only primary benchmark execution.

### 3. Run the source snapshot smoke

From the repo root on Jetson:

```bash
scripts/smoke_jetson_source_env.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

What the script checks:

- required Python runtime dependencies are importable
- `tegrastats` is available
- `python -m inferedge_env.cli doctor` works through `PYTHONPATH`
- `edgeenv doctor` is checked when a console script is available; when `--python`
  points to a conda environment, the script also looks for `edgeenv` next to
  that Python binary
- sampled Jetson profile/config validate
- sampled local run creates `result.json.resource_metrics.source=jetson-tegrastats`
- `runs sampler show` exposes `sample_count`, `warnings`, and raw artifacts
- successful-run export/import preserves `sampler/metadata.json` and `sampler/tegrastats.log`

By default the script uses temporary `/tmp/InferEdgeEnv-jetson-source-*`
directories and deletes only those temporary directories on success. Use
`--keep-artifacts` when recording evidence for a document or handoff note. If
you pass custom `--edgeenv-root` or `--import-root` paths, they must not already
exist; the script will fail instead of deleting user-provided directories.

### 4. Source snapshot behavior

The script sets:

```bash
export PYTHONPATH="<repo-root>:$PYTHONPATH"
```

Then it invokes:

```bash
python -m inferedge_env.cli ...
```

This avoids depending on editable install support in the Jetson Python packaging stack. If `edgeenv` exists in the selected environment, the script also runs `edgeenv doctor` with the same `PYTHONPATH` in place.

### 5. Validation record

Validated on `nano01` using:

```bash
scripts/smoke_jetson_source_env.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

Observed:

```text
EdgeEnv doctor: OK
Valid target profile: jetson-nano-sampled-local
Valid benchmark config: jetson-sampled-local
Run ID: run-20260508-012656-1756a552
Resource metrics: stored (source=jetson-tegrastats, fields=memory_mean_mb, memory_peak_mb, power_mean_w, power_peak_w, temperature_peak_c)
sample_count: 3
raw_artifacts: ["sampler/tegrastats.log"]
Jetson source env smoke passed
```

The script also exported the successful run, imported it into a separate
temporary registry root, and verified that `runs sampler show` still found
`sampler/metadata.json` and `sampler/tegrastats.log` after import.

## 4. HOW NOT — 피해야 할 함정

- Do not present this as remote execution support; it is a local command run on Jetson.
- Do not require editable install for source snapshot validation.
- Do not commit generated `.edgeenv/`, zip exports, raw `tegrastats` logs, models, engines, or datasets.
- Do not make `sampler/metadata.json` a registry source of truth.
- Do not add resource metrics or sampler metadata to comparability gates.

## 5. WHERE — 다른 설계와의 관계

- **Jetson Sampled Run Rehearsal**: uses the smoke script flow to make the observed run reproducible.
- **Packaging And Entrypoint Readiness**: remains the standard local development install path; this document covers Jetson source snapshots.
- **LocalRunner Sampler Wiring Design**: this validates the adapter lifecycle on real `tegrastats`.
- **Sampler Metadata Artifact Policy**: this verifies metadata/raw artifact layout and portability.

## 6. WHY — 배경 판단

During the first Jetson sampled-run rehearsal, the selected system Python lacked runtime dependencies and editable install was not the most reliable path for the transferred source snapshot. The existing `yolo_env` conda environment had the needed runtime dependencies, and `PYTHONPATH` made the source snapshot deterministic without mutating the environment.

Keeping this as a dedicated smoke script gives future Jetson work a repeatable baseline while avoiding package installation churn on the device.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Source snapshot validation on Jetson should prefer `PYTHONPATH` plus a known-good Python environment over assuming editable install support.
