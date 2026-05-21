# inferedge_env/compare 작업 가이드

> Language: [English overview](../../docs/language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 모듈은 무엇을 하는가
두 run의 comparability를 판단한다. 필수 비교 필드가 같으면 same-condition, runtime/execution_provider/target만 다르면 conditional runtime/target comparison으로 표시한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `comparability.py` — comparison rules, reason list, output model
- `regression.py` — comparability-first runtime regression report logic
- `docs/compare-workflow-guide.md` — 사용자가 run 생성부터 compare까지 따라가는 guide
- `examples/benches/local_compare_a.yaml`, `examples/benches/local_compare_b.yaml` — same-condition compare workflow fixtures

기술 스택: Python, Pydantic 또는 dataclasses

## 3. HOW — 일반적인 수정은 어떻게 하는가
비교 규칙은 명시적인 field list로 유지한다. 필드 추가 시 README의 comparability rules와 tests를 먼저 갱신하고, CLI 출력 문구도 함께 확인한다.

`report compare`가 metric delta를 표시할 때는 반드시 `Comparable`/`Mode`/`Reason`을 먼저 출력하고, `Comparable: Yes` + `Mode: same-condition`인 경우에만 보조 정보로 표시한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- runtime/target 차이를 곧바로 `Comparable: No`로 처리하지 말 것 — v1 요구사항은 conditional comparison을 구분한다.
- model hash, input shape, precision, benchmark protocol 차이를 무시하지 말 것 — direct regression comparison이 오판된다.
- 모든 모델을 단일 점수로 줄 세우는 ranking 기능을 넣지 말 것 — EdgeEnv의 목표와 다르다.
- compare workflow 예시에서 metrics 차이만으로 결론을 쓰지 말 것 — 먼저 `Comparable`/`Mode`를 확인해야 한다.
- conditional 또는 non-comparable report에 latency/throughput delta를 표시하지 말 것 — direct regression처럼 오해될 수 있다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: result schema, registry result_path loading
- **피의존**: CLI `report compare`, README, tests
- **경계 / 어댑터**: persisted run evidence를 human-readable comparability judgement로 바꾸는 boundary

## 6. WHY — 코드에 안 적힌 배경 지식
EdgeEnv는 "빠른 결과"보다 "비교 가능한 결과인지"를 먼저 판단한다. 이 모듈은 잘못된 회귀 판단과 과장된 벤치마크 주장을 막는 안전장치다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
