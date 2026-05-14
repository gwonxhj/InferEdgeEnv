# README Quickstart Clean-room Rehearsal

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

외부 사용자를 기다리지 않고, 깨끗한 임시 source snapshot과 새 Python virtual environment에서 README Quickstart를 그대로 실행한 결과를 기록한다.

목표는 `v0.1.2` README 첫 화면과 Quickstart가 repo-local 개발 환경에 기대지 않고 동작하는지 확인하는 것이다.

## 2. CONTENTS — 리허설 범위

Validated from a clean source archive:

- `python -m pip install -e ".[dev]"`
- `edgeenv doctor`
- `python -m inferedge_env.cli doctor`
- fake profile/config validation
- fake benchmark run
- `runs list`
- `runs show`
- local command examples
- resource metric lookup
- same-condition compare
- successful-run export/import

Out of scope:

- Jetson hardware smoke
- Docker/WSL/SSH/remote target behavior
- cloud services, dashboards, public leaderboard, or ranking

## 3. HOW — 실행 절차

Clean-room source setup:

```bash
mktemp -d /private/tmp/inferedgeenv-readme-cleanroom.XXXXXX
git archive --format=tar --output=<tmp>/source.tar HEAD
mkdir -p <tmp>/source
tar -xf <tmp>/source.tar -C <tmp>/source
python -m venv <tmp>/venv
```

README install and entrypoint smoke:

```bash
<tmp>/venv/bin/python -m pip install -e ".[dev]"
<tmp>/venv/bin/edgeenv doctor
<tmp>/venv/bin/python -m inferedge_env.cli doctor
```

README fake run path:

```bash
<tmp>/venv/bin/edgeenv profile validate examples/profiles/local_fake.yaml
<tmp>/venv/bin/edgeenv bench validate examples/benches/yolov8n_fire.yaml
<tmp>/venv/bin/edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
<tmp>/venv/bin/edgeenv runs list
<tmp>/venv/bin/edgeenv runs show <run_id>
```

Extended README flow:

```bash
<tmp>/venv/bin/edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_echo_metrics.yaml
<tmp>/venv/bin/edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
<tmp>/venv/bin/edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
<tmp>/venv/bin/edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
<tmp>/venv/bin/edgeenv runs resources list --metric memory_peak_mb
<tmp>/venv/bin/edgeenv report compare <run_id_a> <run_id_b>
<tmp>/venv/bin/edgeenv runs export <run_id> --output <tmp>/resource-run.zip
<tmp>/venv/bin/edgeenv runs import <tmp>/resource-run.zip --edgeenv-root <tmp>/imported/.edgeenv
```

## 4. HOW NOT — 해석 시 주의할 점

- Do not treat a sandboxed no-network pip failure as an EdgeEnv runtime failure.
- Do not use this clean-room run as a Jetson validation substitute.
- Do not commit generated `<tmp>/.edgeenv`, exported zips, or venv files.
- Do not add Docker/WSL/SSH/cloud setup to README Quickstart to solve local install concerns.
- Do not turn successful compare deltas into ranking claims.

## 5. WHERE — 다른 문서와의 관계

- **README**: this verifies the first user-facing path.
- **v0.1.2 Follow-up Note**: this confirms the recommended starting point works outside the repo workspace.
- **Packaging And Entrypoint Readiness**: this repeats editable install and entrypoint smoke in a clean venv.
- **Release Rehearsal**: this is a narrower external-user rehearsal after the release baseline.
- **Jetson Operations Checklist**: remains the hardware-specific path after local Quickstart succeeds.

## 6. WHY — 배경 판단

External-user confidence does not require waiting for an external person. A clean source archive plus fresh venv catches the most common README drift: missing dependencies, broken console script installation, stale example paths, and examples that only work because the developer's repo root already has state.

The result confirms that `v0.1.2` can be approached as a normal editable Python project and that the first benchmark evidence loop closes without relying on hidden local state.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- README clean-room install requires network or pre-cached build dependencies for `pip install -e ".[dev]"`; a no-network sandbox failure is expected and should be retried with network access before treating it as a product failure.

## Validation Record

Status: passed.

Environment:

```text
source root: /private/tmp/inferedgeenv-readme-cleanroom.nCTrar/source
venv: /private/tmp/inferedgeenv-readme-cleanroom.nCTrar/venv
package version: 0.1.2
```

Observed install:

```text
inferedge-env-0.1.2 editable wheel built successfully
runtime/dev dependencies installed into fresh venv
```

Observed entrypoints:

```text
EdgeEnv doctor: OK
Version: 0.1.2
Runner support: fake, local
Registry: .edgeenv/runs.db
```

Observed fake run:

```text
run_id: run-20260511-160920-058cc047
latency_mean_ms: 12.588
result: .edgeenv/runs/run-20260511-160920-058cc047/result.json
resource_metrics: omitted
```

Observed local/resource/compare flow:

```text
local_echo_metrics run: run-20260511-160949-80ce5b7c
local_resource_metrics run: run-20260511-160949-18aa59fc
local_compare_a run: run-20260511-160949-cafc8e9f
local_compare_b run: run-20260511-160949-f1c820a9
resource lookup: memory_peak_mb=512.0 mb, source=example-script
compare: Comparable: Yes, Mode: same-condition, Metrics Delta present
export/import: passed
```
