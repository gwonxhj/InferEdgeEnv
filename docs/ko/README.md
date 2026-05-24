# EdgeEnv 한국어 README

> Language: [English](../../README.md) | 한국어

InferEdgeEnv는 Edge AI inference benchmark 결과를 local artifact와 SQLite registry로 고정하고, 결과 간 비교 가능성을 판정하는 local-first run evidence registry and comparability checker다. 사용자-facing CLI 명령은 `edgeenv`다.

## v0.1.5에서 시작하기

`v0.1.5`는 현재 v1-complete release baseline이다. InferEdgeEnv v1은 local-first run evidence registry와 comparability checker로 완성 상태이며, 이후 작업은 MVP 미완성이 아니라 v1.1+ 확장으로 분리한다. 첫 사용 경로는 다음 순서가 가장 안전하다.

1. 설치 후 `doctor`를 실행한다.
2. deterministic fake run을 기록한다.
3. local command run을 실행한다.
4. EdgeEnv가 comparability를 판정한 뒤에만 두 run의 metric delta를 읽는다.
5. Jetson 문서는 Jetson shell에서 EdgeEnv를 local로 실행할 준비가 됐을 때만 사용한다.

검증된 범위:

- fake/local benchmark recording
- `.edgeenv/runs/<run_id>/` artifact 저장
- SQLite registry lookup
- export/import
- comparability report
- optional resource metrics
- read-only bundle summary
- Jetson에서 local execution으로 수집하는 optional `tegrastats` sampled evidence

## 빠른 시작

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

Fake benchmark를 먼저 실행한다.

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

그 다음 local command 예제를 실행한다.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_echo_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml
```

두 run을 비교할 때는 먼저 비교 가능성 판단을 읽는다.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv runs list
edgeenv report compare <run_id_a> <run_id_b>
```

runtime regression evidence가 필요하면 같은 comparability gate를 재사용하는
별도 report를 생성한다.

```bash
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

`report regression`은 `same-condition`일 때만 mean/p95/p99/FPS/resource
delta를 계산한다. runtime/provider 또는 target 차이는 각각
`runtime-comparison`, `target-comparison`으로 표시하고, benchmark protocol
mismatch는 `protocol_mismatch`로 표시한다. 이 기능은 local regression
evidence이지 cloud monitoring, public leaderboard, production observability가 아니다.

runtime telemetry history artifact가 있으면 `--telemetry-history`로 연결해
report에 telemetry coverage와 evidence gap을 보조 context로 첨부할 수 있다.
이 context는 same-condition comparability gate를 우회하지 않는다.
`edgeenv runs telemetry inspect-history <path>`로 history artifact의 schema,
replay run, telemetry field, coverage metadata, evidence gap을 먼저 확인할 수
있다. Runtime이 `runtime_telemetry.coverage`를 제공하면 EdgeEnv는 이를
evidence quality metadata로 보존하지만, coverage 누락을 run 실패나 regression
judgement로 승격하지 않는다.
Runtime이 `runtime_telemetry.history_seed`를 제공하면 EdgeEnv는 이를
`runtime_telemetry_history_seed`로 보존하고 `registry_owner=edgeenv`,
`decision_owner=lab` 경계를 검증한다. 이는 local replay/history evidence이며
production monitoring stream이 아니다.

## EdgeEnv가 아닌 것

EdgeEnv는 다음을 구현하지 않는다.

- OS, bootloader, GRUB, BCD, Linux compatibility layer
- VM, Docker, WSL, SSH, cloud target manager
- cloud DB, login/auth, web dashboard, public leaderboard
- model upload server, dataset upload server
- 모든 모델을 하나의 점수로 줄 세우는 ranking system

## InferEdge 계열에서의 위치

InferEdgeLab은 validation / decision layer이고, InferEdgeEnv는 `v0.1.5` v1-complete experiment hygiene / comparability layer다.

InferEdgeEnv는 benchmark evidence를 local artifact, SQLite registry, portable bundle로 고정하고 두 결과를 직접 비교해도 되는지 판정한다. 상위 InferEdge ecosystem에서 Env의 정확한 역할은 generic environment helper가 아니라 local-first run evidence registry and comparability checker다.

InferEdgeOrchestrator도 별도 영역이다. Orchestrator는 배포 이후 scheduling, load shedding, telemetry, runtime coordination을 다루는 post-deployment operation-control layer이고, Env는 live inference operation을 제어하지 않는다.

## Guide Map

한국어 README는 빠른 진입과 프로젝트 경계 확인을 돕기 위한 요약이다. 세부 설계와 최신 release evidence는 영어 대표 문서를 기준으로 확인한다.

영어 대표 경로:

- [README](../../README.md) — 전체 Quickstart와 프로젝트 범위
- [InferEdgeEnv Portfolio Summary](../portfolio_summary.md) — 이 레포의 30초 역할 요약과 reviewer path
- [Documentation Language Guide](../language.md) — 영어 대표 경로와 한국어 진입 경로
- [EdgeEnv v0.1.5 Follow-up Note](../release-follow-up-v0.1.5.md) — 현재 v1-complete 릴리스 기준선과 시작 경로
- [Portfolio Demo Path](../portfolio-demo-path.md) — 리뷰어용 fake/local/compare/export-import/bundle-summary 데모 경로
- [Local Command Contract Guide](../local-command-contract.md) — 사용자 benchmark command 연결 방식
- [Compare Workflow Guide](../compare-workflow-guide.md) — metric delta보다 먼저 comparability를 확인하는 흐름
- [Export/Import Design](../export-import-design.md) — portable evidence bundle contract
- [Schema Versioning And Migration Policy](../schema-versioning-migration-policy.md) — evidence compatibility와 future-version rejection 기준
- [Release Maintenance Checklist](../release-maintenance-checklist.md) — 반복 가능한 release gate

운영 기록:

- [EdgeEnv v0.1.5 Release Rehearsal](../v0.1.5-release-rehearsal.md) — clean-room source archive release gate와 patch 후보 판단
- [EdgeEnv v0.1.4 Follow-up Note](../release-follow-up-v0.1.4.md) — 이전 release quality baseline
- [EdgeEnv v0.1.4 Bilingual Docs Sanity Sweep](../v0.1.4-bilingual-docs-sanity-sweep.md) — README, 한국어 README, 대표 문서 읽기 흐름 점검
- [EdgeEnv v0.1.4 Release Rehearsal](../v0.1.4-release-rehearsal.md) — v0.1.4 후보 전 release quality gate 기록
- [EdgeEnv v0.1.4 Post-release Sanity Sweep](../v0.1.4-post-release-sanity-sweep.md) — README, follow-up note, GitHub Release 문구 점검 기록
- [Release Quality Gate Refresh](../release-quality-gate-refresh.md) — local release smoke와 optional Jetson gate 기준
- [README Quickstart Clean-room Rehearsal](../readme-quickstart-cleanroom-rehearsal.md) — 깨끗한 source archive와 venv에서 README 경로 검증
- [Jetson Measurement Operations Checklist](../jetson-operations-checklist.md) — Jetson 실측 반복 운영 절차
- [Jetson Sampled Evidence Bundle Handoff](../jetson-sampled-evidence-bundle-handoff.md) — sampled bundle export/import와 imported compare 검증
- [EdgeEnv MVP v1 Handoff Status](../v1-handoff-status.md) — 현재 capability snapshot과 future-work 진입점
- [First-user Feedback Backlog](../v0.1.3-user-feedback-backlog.md) — v0.1.5 후보 사용성 관찰을 모으는 기준

설계 참고 문서:

- [InferEdgeEnv Six-Month Quality Roadmap](../six-month-quality-roadmap.md)
- [InferEdgeEnv Portfolio Summary](../portfolio_summary.md)
- [Cross-Repo Positioning Review](../cross-repo-positioning-review.md)
- [Evidence Contract Conformance Suite](../evidence-contract-conformance-suite.md)
- [CLI Error Message Polish](../cli-error-message-polish.md)
- [Local Real Benchmark Example Guide](../local-real-benchmark-example.md)
- [Local Runner Design](../local-runner-design.md)
- [Resource Metrics Design](../resource-metrics-design.md)
- [Sampler Metadata Artifact Policy](../sampler-metadata-artifact-policy.md)
- [Bundle Report Generation Design](../bundle-report-generation-design.md)
