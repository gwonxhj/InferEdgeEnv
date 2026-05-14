# MVP Readiness Checklist

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

EdgeEnv MVP가 현재 어떤 사용자 흐름을 지원하고, 어떤 범위를 의도적으로 지원하지 않는지 release/readiness 관점에서 정리한다.

이 문서는 새 기능 설계가 아니라 v1 기반을 처음 검토하는 사람을 위한 상태판이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `README.md` — 사용자-facing overview와 quickstart
- `docs/local-command-contract.md` — real local command 연결 기준
- `docs/compare-workflow-guide.md` — run 생성부터 compare까지의 end-to-end 흐름
- `docs/local-runner-design.md` — local runner 내부 설계 기준
- `docs/resource-metrics-design.md` — optional resource metrics 정책
- `docs/sampler-failure-policy.md` — sampler/resource evidence 실패 정책
- `docs/ci-readiness.md` — PR/main 자동 검증 기준
- `docs/v1-handoff-status.md` — handoff snapshot과 next work candidates
- `docs/v1-release-rehearsal.md` — main 기준 user-flow rehearsal과 release/tag gate
- `docs/release-maintenance-checklist.md` — 반복 릴리스 운영 gate
- `examples/` — 실행 가능한 deterministic fixtures
- `tests/` — CLI, registry, writer, compare regression coverage

기술 스택: Markdown, Typer CLI, SQLite registry, JSON artifacts, pytest

## 3. HOW — readiness 확인 순서

### User path

1. Install and smoke:

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

2. Record a fake run:

```bash
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
```

3. Record a local command run:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
```

4. Inspect registry and artifacts:

```bash
edgeenv runs list
edgeenv runs show <run_id>
edgeenv runs resources list --metric memory_peak_mb
edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip
edgeenv runs import edgeenv-run-<run_id>.zip
```

5. Compare two runs:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv report compare <run_id_a> <run_id_b>
edgeenv report bundle-summary --scenario same-condition:<run_id_a>:<run_id_b>
```

### Supported in this MVP

- Config validation for benchmark configs and target profiles
- Deterministic `FakeRunner`
- `LocalRunner` with explicit stdout metrics contract
- Local runtime adapter example for user-owned command integration
- Optional resource metrics evidence
- Success artifacts under `.edgeenv/runs/<run_id>/`
- Failed local run artifacts under `.edgeenv/failed-runs/<run_id>/`
- SQLite local registry for successful runs
- Rebuildable `resource_metric_index` for `runs resources list`
- `runs list`, `runs show`, `runs resources list`, `runs export`, `runs import`, `failed-runs list`, `failed-runs show`, `failed-runs export`, `failed-runs import`, `report compare`, and `report bundle-summary`
- Same-condition, conditional, and non-comparable judgement
- Deterministic examples and pytest coverage
- Editable install and `edgeenv` console script smoke path
- GitHub Actions readiness checks for Python 3.10 and 3.11

### Not supported in this MVP

- OS, bootloader, GRUB, BCD, or Linux compatibility behavior
- VM, Docker, WSL, SSH, or cloud target execution
- Cloud DB, login/auth, web dashboard, public leaderboard
- Model or dataset upload server
- Single-score ranking across models
- Resource metrics ranking or comparability gates
- Platform-native sampler adapters beyond wrapper command examples

## 4. HOW NOT — 피해야 할 함정

- README에 구현되지 않은 target path를 quickstart처럼 넣지 않는다.
- Example metrics를 real model performance claim처럼 설명하지 않는다.
- Compare workflow를 leaderboard나 ranking workflow처럼 설명하지 않는다.
- Failed-run artifact를 successful registry record처럼 취급하지 않는다.
- Resource metrics가 없는 run을 낮은 품질 run으로 표시하지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **README**: 이 checklist의 짧은 사용자-facing 버전을 제공한다.
- **Local Command Contract Guide**: 사용자가 자기 command를 붙일 때의 실행 기준이다.
- **Compare Workflow Guide**: MVP의 핵심 가치인 comparability judgement를 end-to-end로 보여준다.
- **Resource Metrics / Sampler Failure docs**: optional evidence와 실패 보존 정책을 설명한다.
- **Export/Import Design**: portable successful/failed evidence bundle contract를 설명한다.
- **V1 Release Rehearsal**: README quickstart가 실제 CLI 흐름으로 닫히는지와 tag gate를 기록한다.

## 6. WHY — 배경 판단

MVP가 커질수록 “무엇이 된다”보다 “무엇을 믿고 따라 해도 되는가”가 중요해진다. 이 checklist는 EdgeEnv가 local-first benchmark evidence runner라는 경계를 유지하면서, 첫 사용자가 검증 가능한 흐름을 순서대로 밟을 수 있게 한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
