# examples 작업 가이드

> Language: [English overview](../docs/language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 모듈은 무엇을 하는가
README와 CLI smoke에 쓰이는 sample benchmark config와 target profile을 보관한다. 사용자가 EdgeEnv MVP를 바로 실행해볼 수 있는 최소 입력이다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택
- `examples/benches/` — benchmark YAML examples
- `examples/profiles/` — target profile YAML examples
- `examples/scripts/` — local smoke에 쓰는 작은 command fixture
- `examples/benches/local_resource_metrics.yaml`와 `examples/scripts/emit_resource_metrics.py` — optional resource metrics local smoke 예시
- `examples/benches/local_sampler_wrapper.yaml`와 `examples/scripts/run_with_sampler.py` — platform tool 없이 wrapper command sampler boundary를 보여주는 예시
- `examples/benches/jetson_tegrastats_local.yaml`, `examples/profiles/jetson_nano_local.yaml`, `examples/scripts/run_with_tegrastats.py` — Jetson `tegrastats`를 local runner stdout contract로 연결하는 예시
- `examples/benches/jetson_sampled_local.yaml`, `examples/profiles/jetson_nano_sampled_local.yaml`, `examples/scripts/emit_delayed_local_metrics.py` — LocalRunner sampler adapter lifecycle을 Jetson `tegrastats`로 검증하는 예시
- `examples/benches/local_sampler_unavailable.yaml`, `examples/benches/local_sampler_malformed_resource.yaml`, `examples/scripts/run_with_sampler_failure_modes.py` — sampler failure policy 실행 예시
- `examples/benches/local_template.yaml`와 `examples/scripts/local_benchmark_template.py` — 실제 benchmark command를 붙일 때 복사해 시작하는 최소 template 예시
- `examples/benches/local_adapter_template.yaml`와 `examples/scripts/adapter_template.py` — 사용자 소유 runtime command를 감싸는 복사 가능한 adapter template 예시
- `examples/benches/local_runtime_adapter.yaml`와 `examples/scripts/local_runtime_adapter_demo.py` — 실제 runtime command adapter pattern을 보여주는 deterministic local 예시
- `examples/benches/local_compare_a.yaml`, `examples/benches/local_compare_b.yaml`, `examples/scripts/emit_compare_metrics.py` — same-condition compare workflow 실행 예시

기술 스택: YAML

## 3. HOW — 일반적인 수정은 어떻게 하는가
schema 변경 시 examples를 가장 먼저 갱신한다. 예시는 작고 deterministic해야 하며 FakeRunner로 실행 가능해야 한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정 (중요)
> 아래 항목은 MVP 프롬프트 기반 추정이므로 구현 중 검토가 필요하다.

- 실제 대형 모델이나 dataset artifact를 repo에 넣지 말 것 — MVP는 upload server나 dataset manager가 아니다.
- Docker/WSL/SSH target 예시를 v1 기본 예시로 넣지 말 것 — 구현되지 않은 기능을 사용자가 실행하게 된다.
- README와 다른 필드명을 쓰지 말 것 — quickstart가 즉시 실패한다.

## 5. WHERE — 다른 모듈과의 의존성
- **의존**: config schema
- **피의존**: README, CLI smoke, tests
- **경계 / 어댑터**: 외부 사용자가 처음 만나는 config contract

## 6. WHY — 코드에 안 적힌 배경 지식
예시는 문서가 아니라 실행 가능한 contract fixture다. 사용자가 복사해 첫 run을 만들 수 있어야 한다. Sampler failure 예시는 정책 문서의 성공/실패 분기를 CLI로 바로 재현할 수 있어야 한다.

_(이 영역의 비명백한 함정·배경 지식이 더 있다면 자유롭게 추가하세요. `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로도 누적 가능합니다.)_

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항
> `learn` 스킬(`/learn` 또는 Codex의 `$learn`)로 누적되는 영역.

_(아직 없음)_
