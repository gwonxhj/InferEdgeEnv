# inferedge_env/utils 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가
hashing과 system info처럼 여러 영역에서 쓰는 작은 helper를 둔다. 핵심 contract를 숨기는 큰 abstraction이 아니라 반복을 줄이는 유틸 영역이다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `hashing.py` — model hash/file hash helper
- `system_info.py` — local env snapshot helper

기술 스택: Python standard library

## 3. HOW — 일반적인 수정은 어떻게 하는가
유틸은 작고 deterministic하게 유지한다. 외부 dependency를 늘리기 전에 standard library로 충분한지 확인하고, edge case는 unit test로 고정한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- model hash 계산 방식을 임의로 바꾸지 말 것 — comparability 판단이 과거 run과 달라진다.
- system info에 민감 정보나 큰 환경 dump를 넣지 말 것 — artifact가 불필요하게 커지고 공유하기 어려워진다.
- util에 CLI/Rich 출력 로직을 넣지 말 것 — 의존 방향이 뒤집힌다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: Python standard library
- **피의존**: config/result/registry/compare
- **경계 / 어댑터**: 공통 low-level helper

## 6. WHY — 코드에 안 적힌 배경 지식
비교 가능성의 핵심은 입력 identity와 실행 context를 안정적으로 남기는 것이다. hashing과 env snapshot은 작지만 result evidence의 신뢰도를 좌우한다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
