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

## 역할 경계 한눈에 보기

| 영역 | EdgeEnv가 담당하는 일 | EdgeEnv가 담당하지 않는 일 |
| --- | --- | --- |
| Run evidence registry | local artifact, SQLite registry row, portable bundle, telemetry history, replay metadata를 저장한다. | Runtime execution을 대체하거나 production telemetry database가 되지 않는다. |
| Comparability judgement | metric delta보다 먼저 same-condition, runtime-comparison, target-comparison, protocol-mismatch 경계를 판정한다. | 모든 모델을 하나의 점수로 ranking하거나 benchmark protocol check를 우회하지 않는다. |
| Runtime regression evidence | comparability gate가 통과된 뒤에만 latency/resource regression을 계산하고 JSON/Markdown evidence를 생성한다. | deployment decision을 만들거나 Lab `deployment_decision`을 덮어쓰거나 AIGuard diagnosis 역할을 하지 않는다. |
| Operation context handoff | Runtime/Orchestrator supplemental telemetry, producer lineage, Lab handoff marker를 traceability evidence로 보존한다. | scheduler, cloud control plane, production observability platform, remote execution proof가 되지 않는다. |

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
한눈에 보는 한국어 해석은
[Runtime Regression Monitor 한국어 Quick Guide](runtime-regression-monitor.md)를
먼저 확인한다.

runtime telemetry history artifact가 있으면 `--telemetry-history`로 연결해
report에 telemetry coverage와 evidence gap을 보조 context로 첨부할 수 있다.
이 context는 same-condition comparability gate를 우회하지 않는다.
`edgeenv runs telemetry inspect-history <path>`로 history artifact의 schema,
replay run, telemetry field, coverage metadata, evidence gap을 먼저 확인할 수
있다. Runtime이 `runtime_telemetry.coverage`를 제공하면 EdgeEnv는 이를
evidence quality metadata로 보존하지만, coverage 누락을 run 실패나 regression
judgement로 승격하지 않는다.
Orchestrator feed가 device-local `candidate_context.producer` lineage를 포함하면
EdgeEnv는
`downstream_guard_alignment.producer_lineage_evidence_type=edgeenv_orchestrator_producer_lineage`
도 함께 검증/보존한다. 이 marker는 producer-lineage reasoning을 queue/thermal
operation evidence와 분리하기 위한 것이며, comparability나 deployment decision
owner를 바꾸지 않는다.
`examples/regression/`에는 live device 없이 downstream handoff를 확인할 수
있는 committed replay fixture matrix가 있다. 이 matrix는 same-condition
regression, `runtime-comparison`, `target-comparison`, `protocol_mismatch`,
telemetry gap, replay sequence context를 포함한다.
`examples/regression/fixture_matrix.json`은 각 fixture role, mode, delta 허용
여부, telemetry/replay context 요구사항을 machine-readable하게 고정한다.
upstream Orchestrator evidence가 remote dispatch starter path에서 온 경우도
EdgeEnv의 역할은 동일하다. EdgeEnv는 worker-selection/fallback/compact event
summary 같은 operation context와
`operation_boundary=remote dispatch starter evidence only` marker를 handoff
traceability로 보존할 수 있지만, production remote execution 완료, long-lived
worker readiness, secure tunnel operation, production retry/failover, cloud
orchestration을 확인하지 않는다. Orchestrator는 operation evidence producer,
AIGuard는 optional deterministic diagnosis provider, Lab은 final deployment
decision owner로 남는다. Orchestrator가 제공한 경우 EdgeEnv가 보존하는 marker는
`evidence_role=remote_dispatch_runtime_event_compact_summary`,
`operation_boundary=remote dispatch starter evidence only`,
`production_remote_execution=false`를 포함하며, 이는 registry/replay
traceability일 뿐 remote 실행 검증이 아니다.
Runtime이 `runtime_telemetry.history_seed`를 제공하면 EdgeEnv는 이를
`runtime_telemetry_history_seed`로 보존하고 `registry_owner=edgeenv`,
`decision_owner=lab` 경계를 검증한다. seed가 `run_config` snapshot을 포함하면
EdgeEnv는 실행 shape, 반복 횟수, timeout, input/preprocess, power mode,
Jetson clocks marker의 field type을 검증하고
`summary.history_seed_run_config_runs`에 반영한다. Runtime Intelligence
handoff manifest는 shape, input mode/preprocess, power mode, Jetson clocks,
warmup/repeat run 같은 compact `history_seed_run_config_markers`도 함께
요약해 Lab이 전체 Runtime result를 다시 해석하지 않고 replay traceability를
확인할 수 있게 한다. 이는 local replay/history evidence이며 production
monitoring stream이 아니다.
Lab-compatible legacy Runtime result fixture에 top-level `run_id`가 없으면
EdgeEnv handoff는 EdgeEnv regression report의 `baseline_run_id` /
`candidate_run_id`를 identity 기준으로 사용한다. 단, Runtime result가
`run_id`를 선언한 경우에는 regression report와 반드시 일치해야 한다.
handoff manifest는 device-local producer lineage와 별도로
`producer_lineage_guard_alignment_run_ids`도 노출해 Lab/AIGuard가
`edgeenv_orchestrator_producer_lineage` marker가 유지된 run을 명확히 확인할
수 있게 한다.
보존된 Orchestrator context에 `runtime_task_event_summary`가 있으면
`orchestrator_task_event_rollup_run_ids`도 함께 노출해 Lab이
`edgeenv_orchestrator_task_event_rollup` evidence row를 downstream gate에서
확인할 수 있게 한다. 이는 deployment decision이 아니라 task-level runtime
operation evidence traceability다.
보존된 Orchestrator context에 `operation_risk_rollup` 또는
`operation_timeline_summary`가 있으면 EdgeEnv는 각각
`orchestrator_operation_risk_rollup_run_ids`와
`orchestrator_operation_timeline_summary_run_ids`도 노출한다. rollup은
`schema_version=inferedge-orchestrator-operation-risk-rollup-v1`,
`operation_context_role=supplemental`, `decision_owner=lab`,
`scheduler_owner=orchestrator`, `not_a_deployment_decision=true` marker를
유지해야 하며, timeline은
`schema_version=inferedge-orchestrator-operation-timeline-summary-v1`를
유지해야 한다. 이 둘은 Lab/AIGuard review context일 뿐 EdgeEnv
comparability gate나 deployment decision이 아니다.
보존된 operation context에 Orchestrator `stale_drop_summary` 또는 timeline
`stale_drop` block이 있으면 EdgeEnv는
`schema_version=inferedge-orchestrator-stale-drop-summary-v1`,
`operation_context_role=supplemental`, `scheduler_owner=orchestrator`,
`decision_owner=lab`, `not_a_deployment_decision=true` marker를 검증하고
`orchestrator_stale_drop_summary_run_ids`로 traceability를 노출한다. 이는
optional operation evidence이며 EdgeEnv regression gate가 아니다.
또한 `lab_bundle_alignment.external_aiguard_required_evidence_types`에
`runtime_history_seed_run_config_traceability`와
`edgeenv_orchestrator_operation_risk_rollup`,
`edgeenv_orchestrator_task_event_rollup`,
`edgeenv_orchestrator_operation_timeline_summary`,
`runtime_queue_overload`, `runtime_thermal_instability`,
`remote_execution_recovered_by_fallback`을
포함해, AIGuard artifact는 외부 산출물로 유지하면서도 Lab Runtime
Intelligence gate가 요구하는 deterministic evidence contract를 EdgeEnv
handoff에 명시한다. 같은 alignment
block은 이 선언이 AIGuard `check-edgeenv-handoff-alignment`와 Lab Runtime
Intelligence bundle manifest gate에서 검증된다는 점도 기록한다.
별도의 `lab_bundle_alignment.optional_aiguard_evidence_types`는 최신
sustained Orchestrator stale-drop context에서 AIGuard가 만들 수 있는
`stale_frame_risk`와 `edgeenv_orchestrator_stale_drop_summary`를 선언한다.
이 둘은 optional이므로 기존 queue/thermal feed나 Lab required bundle set을
깨뜨리지 않는다.
`lab_bundle_alignment.optional_aiguard_source_traceability`는 AIGuard
optional-present source artifact와 재생성 명령을 read-only metadata로
mirror한다:
`InferEdgeAIGuard/examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json`,
`python -m inferedge_aiguard.cli build-runtime-intelligence-optional-stale-drop`.
이는 EdgeEnv handoff와 AIGuard source fixture를 추적 가능하게 할 뿐,
EdgeEnv가 `guard_analysis`를 생성한다는 의미가 아니다.
아래 smoke는 이 producer-side source traceability 경로를 로컬에서 검증한다.
sibling InferEdgeLab checkout이 있으면 생성된 EdgeEnv handoff manifest와
AIGuard optional-present alignment fixture를 Lab source traceability gate로도
검증한다.

```bash
bash scripts/smoke_runtime_intelligence_source_traceability.sh \
  --output-dir reports/runtime_intelligence_source_traceability
```

같은 `lab_bundle_alignment.expected_report_markers`는 downstream Lab report가
보존해야 하는 marker를 producer-side handoff에 명시한다:
`Runtime Intelligence Risk Summary`, `Runtime replay duration scope`,
`Orchestrator operation feed context`, `EdgeEnv fixture matrix coverage`,
`Reviewer operation quick scan`, `Orchestrator task event rollup`,
`Lab EdgeEnv preservation context`,
`AIGuard operation risk rollup evidence`,
`AIGuard task event rollup evidence`,
`AIGuard operation timeline evidence`,
`AIGuard runtime operation anomalies`, `AIGuard remote dispatch event summary`,
`AIGuard remote event summary consistency`,
`Remote fallback starter evidence`,
`lab=Remote fallback starter evidence; evidence=remote_execution_recovered_by_fallback`,
`AIGuard producer-lineage guard alignment`, `Lab remains the final deployment decision owner.`.
EdgeEnv regression context에 optional replay-duration metadata가 있으면
handoff summary는 `duration_source`와 `duration_scope_label`도
`source=entrypoint_requested_frames` 같은 producer-side traceability metadata로
보존한다. 이 목록은 EdgeEnv가 Lab decision을 생성한다는 뜻이 아니라,
Lab-owned report contract와 맞물리는 handoff traceability metadata다.

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
- [Runtime Regression Monitor 한국어 Quick Guide](runtime-regression-monitor.md) — comparability-first runtime regression evidence 한국어 요약
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
