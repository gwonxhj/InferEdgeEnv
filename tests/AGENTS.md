# tests 작업 가이드

> Language: [English overview](../docs/language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 모듈은 무엇을 하는가
EdgeEnv MVP의 pytest 검증을 담당한다. config validation, FakeRunner determinism, result artifact, registry, comparability, CLI smoke를 고정한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `tests/test_config_validation.py` — schema success/failure
- `tests/test_adapter_templates.py` — copyable local adapter template success/failure CLI contract
- `tests/test_evidence_contract_conformance.py` — valid/corrupt evidence stdout contract, failed-run artifact, compare judgement, export/import portability
- `tests/test_fake_runner.py` — deterministic runner output
- `tests/test_result_writer.py` — artifact files
- `tests/test_registry.py` — insert/list/show
- `tests/test_comparability.py` — same/no/conditional
- `tests/test_cli.py` — Typer CLI smoke
- `tests/test_entrypoints.py` — pyproject metadata, module entrypoint, console script smoke

기술 스택: pytest, Typer CliRunner

## 3. HOW — 일반적인 수정은 어떻게 하는가
기능을 추가할 때 최소한 해당 contract를 깨뜨리는 실패 케이스 하나를 같이 추가한다. filesystem/SQLite 테스트는 tmp_path를 사용해 repo의 `.edgeenv`를 오염시키지 않는다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- 테스트가 실제 host 성능이나 시간 랜덤성에 의존하게 하지 말 것 — FakeRunner contract가 흔들린다.
- 테스트 중 repo 루트 `.edgeenv`를 쓰지 말 것 — 개발자의 실제 run registry를 오염시킨다.
- 실패한 테스트가 있는데 commit/push/PR을 진행하지 말 것 — 글로벌 AGENTS 규칙 위반이다.
- entrypoint 테스트는 README의 설치/doctor 경로와 같이 움직여야 한다 — pyproject console script와 package version drift를 놓치지 않는다.
- CI readiness workflow는 `python -m pytest -q`와 README entrypoint smoke를 포함해야 한다 — 로컬 통과와 PR 검증 기준이 갈라지면 안 된다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: 모든 `inferedge_env` 하위 모듈, examples
- **피의존**: CI/수동 검증, PR validation
- **경계 / 어댑터**: MVP 완료 여부를 판단하는 executable spec

## 6. WHY — 코드에 안 적힌 배경 지식
이번 프로젝트는 새 MVP 기반을 빠르게 세우는 단계라 테스트가 설계 문서 역할도 한다. 특히 comparability rules는 테스트로 고정해야 나중에 runner가 늘어도 오판을 막을 수 있다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
