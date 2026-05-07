# inferedge_env/result 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가
run result schema와 `.edgeenv/runs/<run_id>/` artifact writer를 담당한다. `result.json`, config/profile/env/log 파일을 함께 보존해 run 재현성과 조회 가능성을 만든다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `schema.py` — result JSON schema
- `writer.py` — artifact directory와 파일 생성
- `exporter.py` — successful run evidence bundle zip export/import, manifest, checksum generation, safe archive validation

기술 스택: Python, Pydantic, JSON/YAML file IO

## 3. HOW — 일반적인 수정은 어떻게 하는가
result field 변경은 registry insert, runs show, comparability checker, README layout을 함께 점검한다. artifact 추가는 기존 파일명과 하위 호환성을 우선한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- `result.json` schema를 임의로 바꾸지 말 것 — registry와 compare가 같은 run을 해석하지 못한다.
- 성공 run artifact를 `.edgeenv/runs/<run_id>/` 외부에 흩뿌리지 말 것 — local registry layout이 깨진다.
- 실패 run을 성공 run처럼 registry에 insert하지 말 것 — 실패 evidence는 `.edgeenv/failed-runs/<run_id>/`에 분리 보존한다.
- config/profile 원본 복사를 생략하지 말 것 — 나중에 같은 조건인지 검증할 evidence가 사라진다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: config models, target profile, runner output, utils hashing/system info
- **피의존**: registry, CLI runs show, comparability checker, tests
- **경계 / 어댑터**: in-memory run result를 filesystem artifact로 고정하는 boundary

## 6. WHY — 코드에 안 적힌 배경 지식
EdgeEnv의 결과는 점수가 아니라 evidence bundle이다. run artifact는 나중에 compare, report, export/import로 확장될 수 있어야 한다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
