# EdgeEnv MVP v1 Release Rehearsal

## 1. WHAT — 이 문서가 정하는 것

`main` 기준으로 MVP v1 사용자가 실제로 밟을 수 있는 end-to-end 흐름과, 그 흐름을 v1 release/tag 전에 통과해야 하는 기준으로 정리한다.

이 문서는 새 기능 설계가 아니다. 릴리스 직전 점검자가 README quickstart와 핵심 CLI를 그대로 따라 실행했을 때 무엇을 확인해야 하는지 기록한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `README.md` — 사용자-facing quickstart
- `docs/mvp-readiness-checklist.md` — release/readiness 상태판
- `docs/v1-handoff-status.md` — 현재 capability snapshot과 next work candidates
- `docs/compare-workflow-guide.md` — compare 사용자 흐름
- `docs/failed-run-inspection.md` — failed-run diagnostic 흐름
- `docs/export-import-design.md` — successful/failed evidence portability contract
- `docs/resource-query-rehearsal.md` — source/imported registry resource lookup rehearsal
- `docs/jetson-bundle-summary-rehearsal.md` — generated bundle-summary smoke record
- `docs/release-maintenance-checklist.md` — repeatable local, clean-room, optional Jetson, tag, and GitHub Release gate
- `pyproject.toml` — package version and `edgeenv` console script

기술 스택: Typer CLI, local filesystem artifacts, SQLite registry, zip export/import, read-only Markdown reports, pytest, GitHub Actions readiness workflow

## 3. HOW — user-flow rehearsal

### Rehearsal environment

Refreshed on `main` after PR #53:

```text
c34325b Merge pull request #53 from gwonxhj/scripts/bundle-summary-smoke
```

Use a temporary EdgeEnv root so the repo root stays clean:

```bash
mktemp -d /private/tmp/inferedge-env-v1-rehearsal.XXXXXX
```

The recorded run used:

```text
/private/tmp/inferedge-env-release-refresh.QLboSC/.edgeenv
```

### 1. Entrypoint smoke and validation

Commands:

```bash
python -m inferedge_env.cli doctor
edgeenv doctor
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
```

Observed:

- `EdgeEnv doctor: OK`
- `Version: 0.1.2`
- `Runner support: fake, local`
- `Valid target profile: local-fake`
- `Valid benchmark config: yolov8n-fire-fake`

### 2. Successful run lifecycle

Commands:

```bash
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv runs list --edgeenv-root <tmp>/.edgeenv
edgeenv runs show <run_id> --edgeenv-root <tmp>/.edgeenv
edgeenv runs resources list --metric memory_peak_mb --min-value 500 --edgeenv-root <tmp>/.edgeenv
```

Observed:

- fake run stored with `Latency mean: 12.588 ms`
- local template run stored with `Latency mean: 21.4 ms`
- local runtime adapter run stored with `Latency mean: 18.5 ms`
- resource metrics are reported as stored or omitted according to each example
- `runs list` shows successful runs only
- `runs show` returns registry metadata, metrics, model, protocol, runtime, target, and `result_path`
- `runs resources list` shows normalized resource lookup rows such as `memory_peak_mb=512.0 mb`
- resource lookup is a local index convenience, not a ranking or comparability gate

### 3. Compare workflow

Commands:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root <tmp>/.edgeenv
```

Observed same-condition output:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
- latency_mean_ms: 18.0 ms -> 16.4 ms (delta -1.6 ms, -8.89%)
- latency_p50_ms: 17.6 ms -> 16.0 ms (delta -1.6 ms, -9.09%)
- latency_p95_ms: 20.5 ms -> 18.2 ms (delta -2.3 ms, -11.22%)
- latency_p99_ms: 22.0 ms -> 19.7 ms (delta -2.3 ms, -10.45%)
- throughput_fps: 55.5 fps -> 61.0 fps (delta +5.5 fps, +9.91%)
```

Release expectation: metric deltas remain supplemental and appear only after same-condition comparability judgement.

### 4. Successful evidence portability

Commands:

```bash
edgeenv runs export <run_id> --output <tmp>/successful-run.zip --edgeenv-root <tmp>/.edgeenv
edgeenv runs import <tmp>/successful-run.zip --edgeenv-root <tmp>/imported-success/.edgeenv
edgeenv runs show <run_id> --edgeenv-root <tmp>/imported-success/.edgeenv
edgeenv runs resources list --metric memory_peak_mb --min-value 500 --edgeenv-root <tmp>/imported-success/.edgeenv
```

Observed:

- export prints `Run evidence exported`
- import prints `Run evidence imported`
- imported `runs show` succeeds
- imported `result_path` points at the new `.edgeenv/runs/<run_id>/result.json`
- registry row is rebuilt from `result.json`, not copied from the source `runs.db`
- imported `runs resources list` returns the same run id, metric value, unit, and source after rebuilding `resource_metric_index`

### 5. Failed-run diagnostic loop

Commands:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_unavailable.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml --edgeenv-root <tmp>/.edgeenv
edgeenv failed-runs list --edgeenv-root <tmp>/.edgeenv
edgeenv failed-runs show <failed_run_id> --edgeenv-root <tmp>/.edgeenv --log-chars 120
```

Observed:

- unavailable sampler stores a successful primary run with `Resource metrics: omitted`
- malformed resource metrics exits with a clear error
- malformed resource metrics writes `.edgeenv/failed-runs/<run_id>/`
- failed run output includes `Registry: not updated`
- `failed-runs list` and `failed-runs show` inspect failed artifacts without using `runs.db`

### 6. Failed-run diagnostic portability

Commands:

```bash
edgeenv failed-runs export <failed_run_id> --output <tmp>/failed-run.zip --edgeenv-root <tmp>/.edgeenv
edgeenv failed-runs import <tmp>/failed-run.zip --edgeenv-root <tmp>/imported-failed/.edgeenv
edgeenv failed-runs show <failed_run_id> --edgeenv-root <tmp>/imported-failed/.edgeenv --log-chars 0
```

Observed:

- export prints `Failed-run evidence exported`
- import prints `Failed-run evidence imported`
- imported `failed-runs show` succeeds
- failed-run import copies diagnostic evidence into `.edgeenv/failed-runs/<run_id>/`
- failed-run import does not create or update `runs.db`

### 7. Bundle summary report smoke

Commands:

```bash
edgeenv report bundle-summary \
  --scenario same-condition:<run_id_a>:<run_id_b> \
  --edgeenv-root <tmp>/.edgeenv \
  --output <tmp>/bundle-summary.md
```

For sampled Jetson evidence bundle handoff, the repeated release smoke can validate export/import, imported compare, and generated Markdown in one run:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

Observed on `nano01` during PR #53:

- generated `bundle-summary.md` from imported sampled run artifacts
- same-condition summary row had `Metrics Delta` status `present`
- runtime/target conditional summary rows had `Metrics Delta` status `absent`
- generated report did not mutate run artifacts or exported bundles
- report remained human-readable handoff output, not canonical evidence

## 4. HOW NOT — release/tag 전에 피해야 할 함정

- Do not tag if `python -m pytest -q` or GitHub Actions readiness fails.
- Do not tag if the working tree is dirty or `main` is behind `origin/main`.
- Do not tag if README quickstart commands do not match implemented CLI commands.
- Do not tag if successful-run import copies `runs.db` instead of rebuilding from `result.json`.
- Do not tag if failed-run import touches `runs.db`.
- Do not tag if `report compare` prints metric deltas for conditional or non-comparable reports.
- Do not tag if `runs resources list` fails to rebuild lookup rows after successful-run import.
- Do not tag if `report bundle-summary` is written into `.edgeenv/runs/<run_id>/` or exported zip bundles by default.
- Do not tag if any release note implies OS, VM, Docker, WSL, SSH, cloud, auth, dashboard, leaderboard, upload server, or composite ranking support.
- Do not start SSH/Docker/WSL/cloud target implementation as part of the v1 tag gate.

## 5. WHERE — v1 release/tag gate

Recommended next tag for the current package version:

```text
v0.1.2
```

Recommended release title:

```text
EdgeEnv MVP v1
```

Tag only after all of these are true on `main`:

- `pyproject.toml` version matches the intended tag version.
- `python -m pytest -q` passes locally.
- `python -m inferedge_env.cli doctor` passes locally.
- `edgeenv doctor` passes locally.
- README quickstart user-flow rehearsal passes with a temporary `--edgeenv-root`.
- Successful run export/import has been smoke-tested.
- Resource query lookup before and after successful-run import has been smoke-tested.
- Failed-run export/import has been smoke-tested.
- `report bundle-summary` has been smoke-tested or Jetson bundle handoff smoke has been run with `--bundle-summary-output`.
- GitHub Actions readiness passes on Python 3.10 and 3.11.
- `git status --short --branch` reports clean `main...origin/main`.
- Release notes explicitly preserve MVP non-goals.

Suggested tag commands after the gate is satisfied:

```bash
git switch main
git pull --ff-only
git tag -a v0.1.2 -m "EdgeEnv MVP v1 refresh"
git push origin v0.1.2
```

Suggested release notes:

```text
Summary
- EdgeEnv MVP v1 provides a local-first run evidence registry: config-driven fake/local benchmark runs, local artifact storage, SQLite registry lookup, resource metric lookup, comparability judgement, read-only handoff summaries, and portable evidence export/import.
- Successful runs are stored under .edgeenv/runs/<run_id>/ and failed diagnostics under .edgeenv/failed-runs/<run_id>/.
- Compare reports prioritize comparability mode before optional metric deltas.
- Resource metrics remain optional secondary evidence; result.json is canonical and resource_metric_index is rebuildable local lookup state.
- Bundle summaries are human-readable handoff reports and do not replace result artifacts, manifests, sampler metadata, or raw logs.

Validation
- python -m pytest -q
- python -m inferedge_env.cli doctor
- edgeenv doctor
- README user-flow rehearsal with temporary --edgeenv-root
- runs resources list before and after successful-run import
- report bundle-summary or Jetson sampled bundle handoff smoke with --bundle-summary-output
- GitHub Actions readiness: python-3.10, python-3.11

Non-goals
- No OS, VM, Docker, WSL, SSH, cloud, auth, dashboard, leaderboard, upload server, or composite ranking support.
- No remote target execution semantics; Jetson validation runs execute locally on the Jetson.
```

## 6. WHY — 배경 판단

MVP v1의 핵심은 "빠른 기능 추가"가 아니라 사용자가 신뢰할 수 있는 local evidence loop다. Release rehearsal은 이 loop가 실제 CLI command로 닫히는지 확인하고, tag 기준은 accidental scope creep 없이 같은 품질 기준을 반복할 수 있게 만든다.

Jetson sampled validation is now part of the local-first evidence story when hardware is available, but it does not imply SSH or remote target execution. v1 tag gates should keep that boundary explicit.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Export 후 import처럼 archive 생성에 의존하는 rehearsal step은 병렬 실행하지 말고 순차 실행한다.
