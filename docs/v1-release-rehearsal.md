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
- `pyproject.toml` — package version and `edgeenv` console script

기술 스택: Typer CLI, local filesystem artifacts, SQLite registry, zip export/import, pytest, GitHub Actions readiness workflow

## 3. HOW — user-flow rehearsal

### Rehearsal environment

Recorded on `main` after PR #29:

```text
6ca29af feat: add failed run portability
```

Use a temporary EdgeEnv root so the repo root stays clean:

```bash
mktemp -d /private/tmp/inferedge-env-v1-rehearsal.XXXXXX
```

The recorded run used:

```text
/private/tmp/inferedge-env-v1-rehearsal.RvDu3w/.edgeenv
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
```

Observed:

- fake run stored with `Latency mean: 12.588 ms`
- local template run stored with `Latency mean: 21.4 ms`
- local runtime adapter run stored with `Latency mean: 18.5 ms`
- resource metrics are reported as stored or omitted according to each example
- `runs list` shows successful runs only
- `runs show` returns registry metadata, metrics, model, protocol, runtime, target, and `result_path`

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
```

Observed:

- export prints `Run evidence exported`
- import prints `Run evidence imported`
- imported `runs show` succeeds
- imported `result_path` points at the new `.edgeenv/runs/<run_id>/result.json`
- registry row is rebuilt from `result.json`, not copied from the source `runs.db`

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

## 4. HOW NOT — release/tag 전에 피해야 할 함정

- Do not tag if `python -m pytest -q` or GitHub Actions readiness fails.
- Do not tag if the working tree is dirty or `main` is behind `origin/main`.
- Do not tag if README quickstart commands do not match implemented CLI commands.
- Do not tag if successful-run import copies `runs.db` instead of rebuilding from `result.json`.
- Do not tag if failed-run import touches `runs.db`.
- Do not tag if `report compare` prints metric deltas for conditional or non-comparable reports.
- Do not tag if any release note implies OS, VM, Docker, WSL, SSH, cloud, auth, dashboard, leaderboard, upload server, or composite ranking support.
- Do not start Jetson/platform-native sampler adapter implementation as part of the v1 tag gate.

## 5. WHERE — v1 release/tag gate

Recommended tag for the current package version:

```text
v0.1.0
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
- Failed-run export/import has been smoke-tested.
- GitHub Actions readiness passes on Python 3.10 and 3.11.
- `git status --short --branch` reports clean `main...origin/main`.
- Release notes explicitly preserve MVP non-goals.

Suggested tag commands after the gate is satisfied:

```bash
git switch main
git pull --ff-only
git tag -a v0.1.0 -m "EdgeEnv MVP v1"
git push origin v0.1.0
```

Suggested release notes:

```text
Summary
- EdgeEnv MVP v1 provides config-driven fake/local benchmark runs, local artifact storage, SQLite registry lookup, comparability judgement, and portable evidence export/import.
- Successful runs are stored under .edgeenv/runs/<run_id>/ and failed diagnostics under .edgeenv/failed-runs/<run_id>/.
- Compare reports prioritize comparability mode before optional metric deltas.

Validation
- python -m pytest -q
- python -m inferedge_env.cli doctor
- edgeenv doctor
- README user-flow rehearsal with temporary --edgeenv-root
- GitHub Actions readiness: python-3.10, python-3.11

Non-goals
- No OS, VM, Docker, WSL, SSH, cloud, auth, dashboard, leaderboard, upload server, or composite ranking support.
- Jetson/platform-native sampler adapters remain future work.
```

## 6. WHY — 배경 판단

MVP v1의 핵심은 "빠른 기능 추가"가 아니라 사용자가 신뢰할 수 있는 local evidence loop다. Release rehearsal은 이 loop가 실제 CLI command로 닫히는지 확인하고, tag 기준은 accidental scope creep 없이 같은 품질 기준을 반복할 수 있게 만든다.

Jetson이나 platform-native sampler adapter는 다음 큰 단계다. v1 tag는 그 전까지 구현된 local-first capability를 고정하는 boundary로 사용한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Export 후 import처럼 archive 생성에 의존하는 rehearsal step은 병렬 실행하지 말고 순차 실행한다.
