# docs 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가
README와 설계/운영 문서가 위치하는 영역이다. EdgeEnv가 무엇이고 무엇이 아닌지, InferEdge/EdgeBench와 어떤 관계인지 명확히 설명한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `README.md` 또는 root `README.md` — 사용자용 시작 문서
- `docs/` — 설계 메모, 향후 roadmap, Obsidian에서 옮겨온 문서
- `docs/local-runner-design.md` — `target_type: local` runner와 실패 artifact 설계 기준
- `docs/resource-metrics-design.md` — memory/power 같은 optional resource metrics 확장 설계 기준
- `docs/registry-resource-query-design.md` — resource metrics artifact-first 정책과 future registry query migration 기준
- `docs/platform-sampler-design.md` — platform-specific resource sampler boundary와 future adapter 기준
- `docs/sampler-adapter-api-design.md` — future `inferedge_env/samplers/` adapter API, metadata schema, failure taxonomy 기준
- `docs/local-runner-sampler-wiring-design.md` — `LocalRunner`와 sampler adapter lifecycle 연결 방식 기준
- `docs/sampler-metadata-artifact-policy.md` — sampler metadata와 raw artifact 저장 위치, export/import extension 기준
- `docs/sampler-failure-policy.md` — sampler/wrapper failure가 benchmark 성공 여부에 미치는 영향 기준
- `docs/local-command-contract.md` — 사용자가 자기 local benchmark command를 연결할 때 지켜야 하는 stdout/config/troubleshooting contract
- `docs/local-real-benchmark-example.md` — 실제 runtime command adapter pattern을 deterministic local example로 설명하는 guide
- `docs/jetson-tegrastats-wrapper.md` — Jetson `tegrastats` wrapper command를 local runner stdout contract로 연결하는 guide
- `docs/compare-workflow-guide.md` — 두 local run 생성부터 `runs list/show/report compare`까지 이어지는 compare workflow guide
- `docs/failed-run-inspection.md` — failed-run artifact를 `failed-runs list/show/export/import`로 안전하게 확인/이동하는 guide
- `docs/export-import-design.md` — successful run evidence와 failed-run diagnostic bundle zip export/import contract
- `docs/mvp-readiness-checklist.md` — MVP에서 가능한 흐름과 non-goals를 release/readiness 관점으로 정리한 상태판
- `docs/packaging-entrypoints.md` — editable install, module entrypoint, console script readiness 기준
- `docs/ci-readiness.md` — GitHub Actions에서 자동 검증하는 MVP readiness workflow 기준
- `docs/v1-handoff-status.md` — MVP v1 현재 상태, 검증 커맨드, future work, 다음 작업 진입점 snapshot
- `docs/v1-release-rehearsal.md` — main 기준 사용자 흐름 리허설 기록과 v1 release/tag gate 기준
- `inferedge_env/samplers/AGENTS.md` — sampler adapter code 영역 작업 가이드

기술 스택: Markdown

## 3. HOW — 일반적인 수정은 어떻게 하는가
사용자-facing 문서는 CLI/examples/tests와 맞춰서 갱신한다. non-goals는 기능이 늘어날수록 더 명시적으로 유지한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- EdgeEnv를 OS, VM manager, Docker target, WSL target, cloud service처럼 설명하지 말 것 — 프로젝트 포지셔닝이 흐려진다.
- "모든 모델을 한 점수로 줄 세운다"는 표현을 쓰지 말 것 — comparability-first 철학과 충돌한다.
- README 예시를 실행 불가능한 pseudo-config로 두지 말 것 — quickstart 신뢰도가 떨어진다.
- readiness 문서에 future work를 현재 지원 기능처럼 쓰지 말 것 — MVP scope와 non-goals가 흐려진다.
- package name `inferedge-env`, import package `inferedge_env`, console script `edgeenv`를 섞어 쓰지 말 것 — 설치/실행 진입점이 헷갈린다.
- CI readiness에 무거운 benchmark run이나 구현되지 않은 target을 넣지 말 것 — PR 검증이 느려지고 v1 scope가 흐려진다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: CLI command surface, config schema, examples, comparability rules
- **피의존**: 사용자, PR reviewer, Obsidian project notes
- **경계 / 어댑터**: 구현 contract를 사람이 이해하는 product narrative로 바꾸는 boundary

## 6. WHY — 코드에 안 적힌 배경 지식
EdgeEnv는 InferEdge의 validation evidence 철학을 더 작은 benchmark runner/registry 제품으로 분리한 프로젝트다. EdgeBench와 가까운 이름을 갖지만 public leaderboard가 아니라 local comparability checker에 초점을 둔다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
