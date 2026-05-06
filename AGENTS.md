# InferEdgeEnv - Codex/Cursor/Antigravity 작업 지침

> 이 파일은 map 역할을 한다. 작업 시 해당 영역의 `AGENTS.md`를 먼저 읽고 진행한다.
>
> root에 모든 가이드를 몰아넣지 않고 영역별로 분리한 이유는 토큰 효율과 컨텍스트 정확도다.
> 작업 영역만 정확히 참조하면 다른 영역 가이드가 컨텍스트를 오염시키지 않는다.

## 프로젝트 구조

```text
edgeenv/
  cli.py
  config/
  runners/
  registry/
  result/
  compare/
  utils/
examples/
  benches/
  profiles/
tests/
docs/
.agents/
  skills/learn/
  workflows/learn.md
```

## 영역별 가이드

작업 영역에 해당하는 `AGENTS.md`를 먼저 읽고 진행한다.

- **edgeenv/cli.py** — Typer/Rich CLI 진입점과 명령 라우팅 -> [`edgeenv/AGENTS.md`](edgeenv/AGENTS.md)
- **edgeenv/config** — benchmark config와 target profile schema -> [`edgeenv/config/AGENTS.md`](edgeenv/config/AGENTS.md)
- **edgeenv/runners** — runner interface와 FakeRunner -> [`edgeenv/runners/AGENTS.md`](edgeenv/runners/AGENTS.md)
- **edgeenv/result** — result JSON schema와 artifact writer -> [`edgeenv/result/AGENTS.md`](edgeenv/result/AGENTS.md)
- **edgeenv/registry** — local SQLite registry와 run 조회 -> [`edgeenv/registry/AGENTS.md`](edgeenv/registry/AGENTS.md)
- **edgeenv/compare** — comparability checker와 compare 출력 -> [`edgeenv/compare/AGENTS.md`](edgeenv/compare/AGENTS.md)
- **edgeenv/utils** — hashing, system info 같은 작은 공통 유틸 -> [`edgeenv/utils/AGENTS.md`](edgeenv/utils/AGENTS.md)
- **examples** — sample benchmark/profile YAML -> [`examples/AGENTS.md`](examples/AGENTS.md)
- **tests** — pytest 기반 MVP 검증 -> [`tests/AGENTS.md`](tests/AGENTS.md)
- **docs** — README와 설계/운영 문서 -> [`docs/AGENTS.md`](docs/AGENTS.md)

## 영역 가이드의 구조

각 영역의 `AGENTS.md`는 다음 7섹션으로 구성된다.

1. **WHAT** — 이 모듈이 무엇을 하는가
2. **CONTENTS** — 디렉토리 맵과 기술 스택
3. **HOW** — 일반적인 수정은 어떻게 하는가
4. **HOW NOT** — 시스템을 깨뜨리는 비명백한 함정
5. **WHERE** — 다른 모듈과의 의존성
6. **WHY** — 코드에 안 적힌 배경 지식
7. **LEARNED CAUTIONS** — `learn` 스킬로 누적

## 주의사항 학습 (learn 스킬)

작업 중 실수가 발견되면 다음 형태로 호출해 해당 영역 `AGENTS.md`의 "⚠️ LEARNED CAUTIONS" 섹션에 누적한다.

- Claude Code/Cursor/Antigravity: `/learn <메모>` (인자 없이도 호출 가능)
- Codex: `$learn <메모>`

스킬 위치: `.agents/skills/learn/`
