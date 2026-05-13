# inferedge_env 작업 가이드

> 이 가이드는 에이전트가 CLI와 패키지 루트에서 코드를 건드리기 전에 반드시 알아야 할 컨텍스트를 담는다.

## 1. WHAT — 이 모듈은 무엇을 하는가
`inferedge_env`는 EdgeEnv MVP의 Python package 루트다. Typer CLI를 통해 config validation, fake benchmark run, local registry 조회, comparability report를 연결한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `inferedge_env/cli.py` — Typer app, Rich 출력, command orchestration
- `inferedge_env/config/` — Pydantic schema
- `inferedge_env/runners/` — runner interface와 fake runner
- `inferedge_env/result/` — result schema와 artifact writer
- `inferedge_env/registry/` — SQLite run registry
- `inferedge_env/compare/` — comparability checker
- `inferedge_env/report/` — read-only Markdown report generation
- `inferedge_env/utils/` — hashing, system info helper

기술 스택: Python, Typer, Rich, Pydantic, SQLite

## 3. HOW — 일반적인 수정은 어떻게 하는가
CLI 변경은 `inferedge_env/cli.py`에서 시작하되, 실제 도메인 로직은 하위 모듈에 둔다. 명령 추가 시 입력 검증, Rich 출력, 실패 시 명확한 에러 메시지, pytest CLI smoke를 함께 갱신한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- CLI에서 benchmark/result/registry schema를 직접 조립하지 말 것 — result schema compatibility가 깨지면 compare와 registry가 함께 깨진다.
- OS, VM, Docker, WSL, cloud, leaderboard 기능을 CLI에 몰래 추가하지 말 것 — EdgeEnv v1은 local-first run evidence registry/comparability checker다.
- 실패를 조용히 삼키지 말 것 — benchmark artifacts와 registry 상태가 달라지면 재현성이 깨진다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: `config`, `runners`, `result`, `registry`, `compare`, `utils`
- **피의존**: console entrypoint, tests
- **경계 / 어댑터**: CLI는 사용자 인터페이스이고, schema/result/registry contract는 하위 모듈이 소유한다.

## 6. WHY — 코드에 안 적힌 배경 지식
EdgeEnv는 OS나 Linux compatibility layer가 아니라 Edge AI inference benchmark result를 local artifact와 SQLite registry로 고정하는 run evidence registry다. v1의 가치는 실제 런타임 성능을 "하나의 점수"로 줄 세우는 것이 아니라, 결과 evidence와 비교 가능성 판단을 안정적으로 남기는 데 있다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
