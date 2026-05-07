# inferedge_env/samplers 작업 가이드

## 1. WHAT — 이 모듈은 무엇을 하는가

platform-specific resource sampler adapter의 독립 lifecycle과 parser를 담당한다. 현재는 `LocalRunner`에 연결하지 않고, start/stop/summary contract와 Jetson `tegrastats` parser/adapter를 테스트로 검증한다.

## 2. CONTENTS — 파일/디렉토리와 기술 스택

- `base.py` — `SamplerContext`, `SamplerSummary`, `Sampler` protocol, sampler failure taxonomy
- `factory.py` — optional target sampler profile을 concrete sampler adapter로 변환
- `jetson_tegrastats.py` — Jetson `tegrastats` line parser, metadata builder, process adapter

기술 스택: Python standard library subprocess, dataclasses, Protocol, Pydantic `ResourceMetrics`

## 3. HOW — 일반적인 수정은 어떻게 하는가

sampler adapter는 benchmark command를 실행하지 않고 resource evidence만 수집한다. parser는 pure function으로 테스트하고, process lifecycle은 fake process 또는 작은 fixture로 독립 테스트한다.

## 4. ⛔ HOW NOT — 시스템을 깨뜨리는 비명백한 함정

- `LocalRunner`에 sampler lifecycle을 바로 연결하지 않는다.
- sampler failure만으로 primary benchmark result를 버리지 않는다.
- board-level power를 model-only power로 설명하지 않는다.
- resource metrics를 comparability gate로 추가하지 않는다.
- raw sampler artifact를 export/import evidence에 포함하려면 먼저 portability 설계를 갱신한다.

## 5. WHERE — 다른 모듈과의 의존성

- **의존**: `inferedge_env/result/schema.py`의 `ResourceMetrics`
- **피의존**: future runner integration, examples wrapper, docs
- **경계 / 어댑터**: platform-specific output을 EdgeEnv normalized resource evidence로 바꾸는 boundary

## 6. WHY — 코드에 안 적힌 배경 지식

Jetson wrapper로 실측 경로는 검증됐지만, adapter API는 플랫폼별 차이를 흡수해야 한다. 그래서 첫 구현은 `LocalRunner` wiring 없이 독립 parser/lifecycle module로 유지한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
