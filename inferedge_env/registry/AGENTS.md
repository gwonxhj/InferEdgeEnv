# inferedge_env/registry 작업 가이드

> Language: [English overview](../../docs/language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 모듈은 무엇을 하는가
`.inferedge_env/runs.db` SQLite registry를 담당한다. run_id, created_at, target/model/runtime/protocol/metrics/result_path를 저장하고 `runs list/show` 조회를 지원한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `db.py` — SQLite connection, schema migration/init, insert/list/show
- `models.py` — registry record model
- `artifacts.py` — run artifact path helper

기술 스택: Python, sqlite3, Pydantic 또는 typed dict

## 3. HOW — 일반적인 수정은 어떻게 하는가
DB schema 변경은 migration 성격의 init logic과 tests를 함께 수정한다. registry에는 result JSON 전체가 아니라 조회/필터에 필요한 summary와 `result_path`를 저장한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- cloud DB나 auth 계층을 추가하지 말 것 — v1 registry는 local-first SQLite다.
- result artifact와 registry insert를 서로 다른 run_id로 처리하지 말 것 — 조회와 파일 evidence가 분리된다.
- metrics를 문자열 blob으로만 저장하지 말 것 — list/show 출력과 테스트 검증이 어려워진다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: result writer/schema, filesystem layout
- **피의존**: CLI `runs list`, `runs show`, `report compare`, tests
- **경계 / 어댑터**: file artifact를 local query index로 노출하는 boundary

## 6. WHY — 코드에 안 적힌 배경 지식
SQLite registry는 public leaderboard가 아니다. 개인/로컬 개발 환경에서 run history를 빠르게 찾기 위한 색인이다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
