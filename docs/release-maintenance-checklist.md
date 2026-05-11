# EdgeEnv Release Maintenance Checklist

## 1. WHAT — 이 문서가 정하는 것

반복 릴리스 작업자가 `main`을 다음 tag로 고정하기 전에 확인해야 할 최소 절차를 한 장으로 정리한다.

이 문서는 새 기능 설계나 자동화 spec이 아니다. `docs/v1-release-rehearsal.md`의 gate를 운영 체크리스트로 압축해, local tests, clean-room rehearsal, optional Jetson smoke, tag, GitHub Release 작성 순서를 반복 가능하게 만든다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `README.md` — 사용자-facing quickstart와 guide map
- `pyproject.toml` — package version
- `docs/v1-release-rehearsal.md` — full release/tag gate와 user-flow rehearsal
- `docs/readme-quickstart-cleanroom-rehearsal.md` — clean source archive + fresh venv 검증 기록
- `docs/jetson-operations-checklist.md` — optional Jetson 반복 운영 절차
- `docs/release-follow-up-v0.1.2.md` — release follow-up note 형식
- `docs/v0.1.3-candidate-plan.md` — v0.1.3 polish 작업 순서

기술 스택: Markdown, pytest, Typer CLI, GitHub Actions, GitHub Release

## 3. HOW — 릴리스 반복 절차

### 1. Scope Freeze

- `main`에 포함할 PR이 모두 merge됐는지 확인한다.
- 다음 tag에 들어가지 않을 작업은 새 브랜치에 남겨 둔다.
- release note에 넣을 사용자-facing 변화만 짧게 적는다.
- non-goals를 다시 확인한다: OS/VM/Docker/WSL/SSH/cloud/auth/dashboard/leaderboard/upload/composite ranking은 여전히 제외한다.

### 2. Local Gate

`main` 기준으로 최신 상태를 맞춘다.

```bash
git switch main
git pull --ff-only
git status --short --branch
```

필수 검증:

```bash
python -m pytest -q
git diff --check
python -m inferedge_env.cli doctor
edgeenv doctor
```

성공 기준:

- pytest가 모두 통과한다.
- whitespace diff 문제가 없다.
- module entrypoint와 console script가 모두 동작한다.
- `git status --short --branch`가 clean `main...origin/main` 상태다.

### 3. README Quickstart Smoke

임시 root를 사용해 repo를 더럽히지 않는다.

```bash
work_root=$(mktemp -d /private/tmp/inferedge-release-smoke.XXXXXX)
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv runs list --edgeenv-root "$work_root/.edgeenv"
edgeenv runs show <run_id> --edgeenv-root "$work_root/.edgeenv"
```

Resource query와 export/import 경계도 확인한다.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv runs resources list --metric memory_peak_mb --json --edgeenv-root "$work_root/.edgeenv"
edgeenv runs export <run_id> --output "$work_root/run.zip" --edgeenv-root "$work_root/.edgeenv"
edgeenv runs import "$work_root/run.zip" --edgeenv-root "$work_root/imported.edgeenv"
edgeenv runs resources list --metric memory_peak_mb --json --edgeenv-root "$work_root/imported.edgeenv"
```

성공 기준:

- successful run은 `.edgeenv/runs/<run_id>/`에 저장된다.
- imported registry는 `result.json`에서 rebuild된다.
- resource query JSON은 `filters`, `sources`, `unit`, `source`를 보여주지만 ranking이나 comparability gate를 만들지 않는다.

### 4. Compare And Report Smoke

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root "$work_root/.edgeenv"
edgeenv report bundle-summary --scenario same-condition:<run_id_a>:<run_id_b> --edgeenv-root "$work_root/.edgeenv" --output "$work_root/bundle-summary.md"
```

성공 기준:

- compare output은 `Comparable`, `Mode`, `Reason`을 먼저 보여준다.
- metric delta는 `Comparable: Yes` + `Mode: same-condition`에서만 보조 정보로 나온다.
- bundle summary는 read-only Markdown output이고 run artifact나 exported zip을 수정하지 않는다.

### 5. Failed-run Portability Smoke

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs list --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs show <failed_run_id> --edgeenv-root "$work_root/.edgeenv" --log-chars 120
edgeenv failed-runs export <failed_run_id> --output "$work_root/failed-run.zip" --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs import "$work_root/failed-run.zip" --edgeenv-root "$work_root/imported-failed.edgeenv"
edgeenv failed-runs show <failed_run_id> --edgeenv-root "$work_root/imported-failed.edgeenv" --log-chars 0
```

성공 기준:

- malformed resource metrics는 failed-run artifact로 보존된다.
- failed-run import는 `.edgeenv/failed-runs/<run_id>/`만 채우고 `runs.db`를 만들거나 수정하지 않는다.

### 6. Optional Clean-room Gate

릴리스 직전 README 신뢰도를 다시 확인해야 하면 `docs/readme-quickstart-cleanroom-rehearsal.md` 방식으로 source archive + fresh venv에서 다음을 확인한다.

```bash
python -m pip install -e ".[dev]"
edgeenv doctor
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
```

이 단계는 package metadata나 README Quickstart를 바꾼 릴리스에서는 사실상 필수로 본다.

### 7. Optional Jetson Gate

Jetson sampled evidence나 sampler 관련 변경이 포함됐거나, hardware-backed evidence baseline을 새로 고정하려면 nano01 같은 실제 장비에서 `docs/jetson-operations-checklist.md`를 따른다.

최소 확인:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

성공 기준:

- Jetson에서 EdgeEnv가 local execution으로 실행된다.
- sampled runs는 optional resource/sampler evidence를 보존한다.
- exported/imported bundle compare와 bundle summary가 protocol-first 판단을 유지한다.
- 이 결과를 SSH target support로 표현하지 않는다.

### 8. GitHub Gate

- PR checks가 Python 3.10과 3.11에서 통과했는지 확인한다.
- failed check, pending required check, unreviewed high-risk diff가 있으면 tag를 만들지 않는다.
- release branch가 아니라 `main`의 commit을 tag한다.

### 9. Tag And Release

`pyproject.toml` version과 tag 이름이 일치하는지 확인한 뒤 tag를 만든다.

```bash
git tag -a vX.Y.Z -m "EdgeEnv vX.Y.Z"
git push origin vX.Y.Z
```

GitHub Release 본문에는 다음 네 구역을 유지한다.

```text
Summary
- 사용자-facing 변화만 적는다.

Validation
- python -m pytest -q
- python -m inferedge_env.cli doctor
- edgeenv doctor
- README smoke or clean-room rehearsal
- GitHub Actions python-3.10, python-3.11
- optional Jetson smoke, if run

Impact
- local evidence loop에 어떤 신뢰도가 추가됐는지 적는다.

Non-goals
- OS/VM/Docker/WSL/SSH/cloud/auth/dashboard/leaderboard/upload/composite ranking은 제외한다.
```

### 10. Post-release Follow-up

- README 상단이나 follow-up note가 새 tag를 가리키는지 확인한다.
- `docs/v1-handoff-status.md` 또는 새 release follow-up note에 다음 작업 후보를 짧게 남긴다.
- 릴리스 후 바로 새 기능을 시작하지 말고 README Quickstart를 외부 사용자 관점으로 한 번 더 읽는다.

## 4. HOW NOT — 피해야 할 함정

- 테스트 실패, pending CI, dirty working tree 상태에서 tag를 만들지 않는다.
- generated `.edgeenv/`, zip bundle, model, engine, dataset, stdout/stderr artifact를 commit하지 않는다.
- release note에 future work를 현재 지원 기능처럼 쓰지 않는다.
- Jetson local execution 검증을 SSH/remote target 지원처럼 설명하지 않는다.
- resource metrics나 bundle summary를 canonical evidence 또는 ranking surface처럼 설명하지 않는다.
- `report compare`의 protocol-first 판단보다 metric delta를 앞세우지 않는다.

## 5. WHERE — 다른 문서와의 관계

- **V1 Release Rehearsal**: full gate와 실제 관측 기록을 보관한다.
- **MVP Readiness Checklist**: 현재 지원/비지원 기능 상태판이다.
- **README Quickstart Clean-room Rehearsal**: install/entrypoint 신뢰도를 깨끗한 환경에서 확인한다.
- **Jetson Operations Checklist**: hardware-backed sampled evidence 반복 운영 절차다.
- **Release Follow-up Note**: release 이후 사용자가 어디서 시작할지 짧게 보여준다.

## 6. WHY — 배경 판단

EdgeEnv 릴리스는 기능 수를 늘리는 행위가 아니라, local-first evidence loop를 믿을 수 있는 기준선으로 고정하는 행위다. 체크리스트가 짧아야 반복되고, 반복돼야 release note가 과장 없이 유지된다.

이 문서는 `v0.1.3` 이후에도 재사용할 수 있게 version-specific output보다 gate와 판단 기준을 중심으로 쓴다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Release maintenance checklist는 자동화가 아니라 gate 문서다. tag/release 생성은 tests, smoke, CI가 실제로 통과한 뒤에만 수행한다.
