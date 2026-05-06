# inferedge_env/config 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가
benchmark config와 target profile의 Pydantic schema를 소유한다. EdgeEnv가 어떤 run을 같은 조건으로 볼 수 있는지 판단하는 원천 입력을 검증한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `bench_config.py` — benchmark config schema와 YAML loading
- `target_profile.py` — target profile schema와 YAML loading

기술 스택: Python, Pydantic, YAML

## 3. HOW — 일반적인 수정은 어떻게 하는가
필드 추가/변경은 README 예시, examples, CLI validate, tests를 함께 갱신한다. 비교 가능성에 영향을 주는 필드는 `inferedge_env/compare` 테스트까지 확인한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- 필수 필드를 optional로 느슨하게 만들지 말 것 — 불완전한 run이 registry에 저장되어 compare 판정이 흔들린다.
- `target_type`에 Docker/WSL/SSH 구현을 추가하지 말 것 — v1은 `fake`, `local`만 허용하고 SSH는 구조만 열어둔다.
- input shape, precision, protocol 필드명을 임의 변경하지 말 것 — result JSON과 comparability contract가 깨진다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: YAML parser, Pydantic
- **피의존**: CLI validate/run, FakeRunner, result writer, comparability checker, tests
- **경계 / 어댑터**: 외부 YAML과 내부 typed model 사이의 contract boundary

## 6. WHY — 코드에 안 적힌 배경 지식
EdgeEnv는 환경을 표준화하지 않고 결과 기록과 비교 판단을 표준화한다. 따라서 config schema는 "실행 방법"뿐 아니라 "비교 가능한 조건"을 보존하는 역할을 한다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
