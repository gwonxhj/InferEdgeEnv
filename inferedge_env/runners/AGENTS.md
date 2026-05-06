# inferedge_env/runners 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가
runner interface와 v1 FakeRunner를 담당한다. 실제 모델 실행 없이 deterministic benchmark result를 만들어 CLI, result writer, registry 흐름을 검증한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `base.py` — runner protocol/base interface
- `fake.py` — deterministic fake benchmark runner
- `local.py` — subprocess 기반 local benchmark command runner

기술 스택: Python, dataclasses 또는 Pydantic model, typing protocol

## 3. HOW — 일반적인 수정은 어떻게 하는가
새 runner는 base interface를 따르게 추가한다. v1에서는 FakeRunner의 deterministic metrics가 테스트 fixture처럼 안정적으로 유지되어야 한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- FakeRunner latency를 randomness나 host 성능에 의존하게 만들지 말 것 — 테스트와 예시 결과가 매번 달라진다.
- SSH/WSL/Docker runner를 구현하지 말 것 — local runner와 target boundary가 섞이면 v1 범위를 넘는다.
- local runner에서 stdout 숫자를 추측하지 말 것 — `EDGEENV_METRICS_JSON=` contract만 metrics source로 사용해야 한다.
- local runner에서 `shell=True`를 쓰거나 `extra_env`로 `EDGEENV_` 예약 값을 덮어쓰지 말 것 — command execution boundary와 EdgeEnv context가 깨진다.
- stdout/stderr 필드를 생략하지 말 것 — artifact writer가 run evidence를 완성하지 못한다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: config schema, target profile
- **피의존**: CLI `bench run`, result writer, registry tests
- **경계 / 어댑터**: runner output은 result schema로 변환되는 raw execution evidence다.

## 6. WHY — 코드에 안 적힌 배경 지식
FakeRunner는 "가짜 성능 주장"이 아니라 전체 run lifecycle을 안전하게 개발하기 위한 deterministic harness다. LocalRunner는 현재 머신 command 실행과 명시적 metrics JSON capture만 담당하며, SSH/WSL/Docker는 별도 future target으로 둔다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
