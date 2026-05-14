# Jetson Measurement Operations Checklist

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

`v0.1.4` 이후 Jetson에서 sampled benchmark를 반복 실행할 때 확인할 운영 체크리스트를 정한다. 목표는 매번 같은 기준으로 환경을 확인하고, evidence를 보관하고, 실패 시 어디서부터 triage할지 빠르게 판단하는 것이다.

이 문서는 새 기능 설계가 아니다. SSH target, remote runner, model server, dashboard, leaderboard를 추가하지 않는다. Jetson에 접속한 뒤 Jetson shell에서 InferEdgeEnv local runner와 optional `jetson-tegrastats` sampler를 실행하는 운영 기준이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `docs/v1-release-rehearsal.md` — 현재 release/tag gate 기준
- `docs/jetson-env-setup-hardening.md` — Jetson source snapshot과 Python 환경 기준
- `docs/jetson-sampled-run-rehearsal.md` — single sampled run 검증 기록
- `docs/jetson-sampled-evidence-bundle-handoff.md` — sampled bundle export/import 검증 기록
- `docs/jetson-bundle-summary-rehearsal.md` — imported bundle summary 검증 기록
- `scripts/smoke_jetson_source_env.sh` — single sampled run smoke
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — same/runtime/target sampled bundle handoff smoke
- `examples/profiles/jetson_nano_sampled_local.yaml` — sampled Jetson local profile
- `examples/benches/jetson_sampled_local.yaml` — deterministic sampled benchmark config

기술 스택: Jetson Linux, conda Python, `PYTHONPATH`, `tegrastats`, EdgeEnv local runner, `.edgeenv` artifact root, zip evidence bundle, Markdown handoff summary

## 3. HOW — 반복 운영 절차

### 1. Before connecting

Host-side checks:

```bash
git switch main
git pull --ff-only
git status --short --branch
git tag --list "v0.1.4"
```

Expected:

- working tree is clean
- `main` is aligned with `origin/main`
- current release baseline tag exists

Do not start a new measurement run from an unknown branch unless the goal is explicitly to validate that branch. If the rehearsal itself is being documented on a feature branch, compare that branch's base commit with `origin/main` instead of running a branch-local `git pull --ff-only`.

When Jetson does not already have a current source snapshot, create and transfer one from the host:

```bash
git archive --format=tar --output=/tmp/inferedgeenv-v0.1.4-ops.tar HEAD
scp /tmp/inferedgeenv-v0.1.4-ops.tar risenano01@nano01.local:/tmp/inferedgeenv-v0.1.4-ops.tar
```

Then unpack it into a fresh Jetson source directory:

```bash
mkdir -p /tmp/InferEdgeEnv-jetson-ops-source
tar -xf /tmp/inferedgeenv-v0.1.4-ops.tar -C /tmp/InferEdgeEnv-jetson-ops-source
cd /tmp/InferEdgeEnv-jetson-ops-source
```

### 2. On Jetson, confirm the environment

Run from the Jetson shell:

```bash
hostname
uname -a
command -v tegrastats
/home/risenano01/miniconda3/envs/yolo_env/bin/python --version
/home/risenano01/miniconda3/envs/yolo_env/bin/python - <<'PY'
import typer, rich, pydantic, yaml
print("EdgeEnv runtime dependencies: OK")
PY
```

Expected:

- hostname matches the intended device, for example `nano01`
- kernel is Jetson Linux, for example `5.15.148-tegra aarch64`
- `tegrastats` is available
- selected Python can import EdgeEnv runtime dependencies

For source snapshot runs, prefer:

```bash
/home/risenano01/miniconda3/envs/yolo_env/bin/python -m inferedge_env.cli doctor
```

The `edgeenv` console script may not be on PATH in a non-interactive SSH command. The smoke scripts still check the selected Python environment and use `PYTHONPATH` so the source snapshot path remains deterministic.

### 3. Use a fresh operations root

Use one top-level directory per rehearsal or measurement session:

```bash
export EDGEENV_OP_ROOT=/tmp/InferEdgeEnv-jetson-ops-$(date +%Y%m%d-%H%M%S)
mkdir -p "$EDGEENV_OP_ROOT/reports"
```

Suggested layout:

```text
$EDGEENV_OP_ROOT/
  single/source/.edgeenv/
  single/imported/.edgeenv/
  handoff/source/.edgeenv/
  handoff/imported/.edgeenv/
  handoff/bundles/
  reports/
```

Keep generated evidence under this root until the run is reviewed. Do not place generated `.edgeenv` roots or exported bundles inside the git worktree unless the directory is explicitly ignored and temporary.

### 4. Run the smoke path first

For a single sampled run:

```bash
scripts/smoke_jetson_source_env.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --edgeenv-root "$EDGEENV_OP_ROOT/single/source/.edgeenv" \
  --import-root "$EDGEENV_OP_ROOT/single/imported/.edgeenv" \
  --keep-artifacts
```

For release-level sampled bundle handoff:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv" \
  --import-root "$EDGEENV_OP_ROOT/handoff/imported/.edgeenv" \
  --bundle-dir "$EDGEENV_OP_ROOT/handoff/bundles" \
  --bundle-summary-output "$EDGEENV_OP_ROOT/reports/bundle-summary.md" \
  --bundle-summary-source-device "$(hostname)" \
  --keep-artifacts
```

Expected:

- sampled runs store `resource_metrics.source=jetson-tegrastats`
- `sampler/metadata.json` exists for sampled successful runs
- raw sampler artifact `sampler/tegrastats.log` exists when listed in metadata
- exported bundles exclude `runs.db`
- imported runs rebuild registry rows from `result.json`
- same-condition compare keeps `Metrics Delta`
- runtime/target conditional compares suppress `Metrics Delta`
- bundle summary is generated outside `.edgeenv/runs/<run_id>/`

### 5. Inspect successful evidence

Useful commands:

```bash
python -m inferedge_env.cli runs list --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv"
python -m inferedge_env.cli runs show <run_id> --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv"
python -m inferedge_env.cli runs sampler show <run_id> --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv"
python -m inferedge_env.cli runs resources list --metric memory_peak_mb --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv"
```

Replace `handoff/source/.edgeenv` with `single/source/.edgeenv` when inspecting the single sampled run smoke.

Record these in handoff notes:

- repo commit or release tag used
- Jetson hostname and kernel
- Python interpreter path and version
- source `.edgeenv` root
- imported `.edgeenv` root
- bundle directory
- generated report path
- run ids grouped by same-condition, runtime-conditional, target-conditional scenarios

### 6. Preserve evidence for handoff

Keep these artifacts together:

```text
$EDGEENV_OP_ROOT/handoff/source/.edgeenv/runs/<run_id>/
$EDGEENV_OP_ROOT/handoff/imported/.edgeenv/runs/<run_id>/
$EDGEENV_OP_ROOT/handoff/bundles/edgeenv-run-<run_id>.zip
$EDGEENV_OP_ROOT/reports/bundle-summary.md
```

Canonical evidence:

- `result.json`
- `config.yaml`
- `target.yaml`
- `env.json`
- `stdout.log`
- `stderr.log`
- export manifest and checksums inside each zip

Supplemental evidence:

- `sampler/metadata.json`
- `sampler/tegrastats.log`
- `resource_metrics` in `result.json`
- `reports/bundle-summary.md`

`reports/bundle-summary.md` is a human handoff aid. It does not replace zip manifests, checksums, run artifacts, or compare output.

### 7. Failure triage

Use this order:

1. Environment failure: check Python path, dependency imports, and `command -v tegrastats`.
2. Source snapshot failure: confirm `PYTHONPATH` points to the repo root used for the run.
3. Primary benchmark failure: inspect `.edgeenv/failed-runs/<run_id>/stdout.log`, `stderr.log`, `config.yaml`, and `target.yaml`.
4. Sampler unavailable: if sampler is optional, primary benchmark may still succeed with resource metrics omitted.
5. Malformed resource metrics: expect a failed-run diagnostic artifact rather than a successful registry row.
6. Import failure: inspect zip manifest, checksum mismatch, missing files, unsafe paths, or duplicate run id.
7. Compare/report drift: verify `report compare` starts with `Comparable`, `Mode`, and `Reason`; metric deltas must appear only for `Comparable: Yes` and `Mode: same-condition`.

Useful diagnostic commands:

```bash
python -m inferedge_env.cli failed-runs list --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv"
python -m inferedge_env.cli failed-runs show <failed_run_id> --edgeenv-root "$EDGEENV_OP_ROOT/handoff/source/.edgeenv" --log-chars 200
python -m inferedge_env.cli report compare <run_id_a> <run_id_b> --edgeenv-root "$EDGEENV_OP_ROOT/handoff/imported/.edgeenv"
python -m inferedge_env.cli report bundle-summary --help
```

## 4. HOW NOT — 피해야 할 함정

- Do not describe this as SSH target support; SSH is only a way to reach the Jetson shell.
- Do not run repeated measurements into a reused `.edgeenv` root unless the intent is to accumulate that registry.
- Do not delete generated evidence before export/import and compare checks are reviewed.
- Do not commit `.edgeenv/`, zip bundles, raw `tegrastats` logs, models, engines, or datasets.
- Do not treat resource metrics or sampler metadata as comparability gates.
- Do not treat `resource_metric_index` or `runs.db` as canonical evidence; both are local registry/index state.
- Do not place generated bundle summaries inside exported zip bundles by default.
- Do not turn successful/conditional comparisons into a ranking or composite score.

## 5. WHERE — 다른 문서와의 관계

- **Release Rehearsal**: this checklist is the operational companion to the current `v0.1.4` release gate.
- **Jetson Environment Setup Hardening**: use it when Python or `PYTHONPATH` setup is unclear.
- **Jetson Sampled Run Rehearsal**: use it for single sampled run expectations and concrete observed output.
- **Jetson Sampled Evidence Bundle Handoff**: use it for export/import and imported compare integrity.
- **Jetson Bundle Summary Rehearsal**: use it for generated Markdown summary expectations.
- **Failed Run Inspection Guide**: use it when a benchmark command creates diagnostic artifacts.

## 6. WHY — 배경 판단

After `v0.1.4`, the useful next improvement is not more scope but repeatability. Jetson evidence can be convincing only when the environment, run roots, exported bundles, imported registry, and handoff report are collected consistently.

This checklist keeps the operation local-first: the Jetson executes the benchmark locally, EdgeEnv records artifacts locally, and exported bundles move evidence without smuggling registry state or turning sampled resource data into a compare gate.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Repeated Jetson measurements should use a fresh operation root and record source/imported/bundle/report paths together; otherwise evidence handoff becomes hard to audit later.
- When documenting an operations rehearsal on a feature branch, do not run the checklist's `git pull --ff-only` literally on that branch; verify the branch is based on `origin/main` instead.
- Non-interactive Jetson SSH sessions may not expose the `edgeenv` console script on PATH; use the selected Python with `python -m inferedge_env.cli` for manual inspection commands.

## Validation Record — nano01

Status: passed on `nano01`.

Host baseline:

```text
local branch: docs/jetson-operations-rehearsal
base commit: d2b5d5c36ced25a8ee930877a7dcf80c04385cde
origin/main: d2b5d5c36ced25a8ee930877a7dcf80c04385cde
release tag present: v0.1.2
```

Jetson environment:

```text
hostname: nano01
platform: Linux 5.15.148-tegra aarch64
tegrastats: /usr/bin/tegrastats
python: /home/risenano01/miniconda3/envs/yolo_env/bin/python, Python 3.10.12
runtime dependencies: OK
```

Source snapshot:

```text
/tmp/InferEdgeEnv-jetson-ops-source.YHI7Rg
```

Operation root:

```text
/tmp/InferEdgeEnv-jetson-ops.vT1m9R
```

Observed nuance:

- `python -m inferedge_env.cli doctor` passed with `Version: 0.1.2`.
- `edgeenv doctor` was not available through the non-interactive SSH PATH before the smoke script set up the selected source snapshot environment.

Single sampled run smoke:

```text
status: passed
run_id: run-20260508-070651-4d28f5d3
edgeenv_root: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/single/source/.edgeenv
import_root: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/single/imported/.edgeenv
resource_metrics.source: jetson-tegrastats
sample_count: 3
raw_artifacts: sampler/tegrastats.log
memory_peak_mb: 885.0
power_peak_w: 4.515
temperature_peak_c: 42.531
```

Sampled bundle handoff smoke:

```text
status: passed
source root: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/handoff/source/.edgeenv
imported root: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/handoff/imported/.edgeenv
bundle dir: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/handoff/bundles
bundle summary: /tmp/InferEdgeEnv-jetson-ops.vT1m9R/reports/bundle-summary.md
```

Observed run pairs:

```text
same-condition:
run-20260508-070711-03f7ca35
run-20260508-070713-9498e0df

runtime-conditional:
run-20260508-070716-09c90867
run-20260508-070719-08511b90

target-conditional:
run-20260508-070721-e1f9ded9
run-20260508-070724-9dc2f2a6
```

Observed checks:

- all six handoff runs stored `resource_metrics.source=jetson-tegrastats`
- all six handoff runs had `sampler/metadata.json`
- all six handoff runs had raw artifact `sampler/tegrastats.log`
- exported bundles contained core files plus sampler metadata/raw log
- imported registry rebuilt from `result.json`
- same-condition imported compare printed `Metrics Delta`
- runtime/target conditional imported compares suppressed `Metrics Delta`
- generated bundle summary listed same-condition delta as `present` and conditional deltas as `absent`
- `runs resources list --metric memory_peak_mb` showed six Jetson resource rows
- `failed-runs list` reported no failed run artifacts
