# Platform Sampler Design

## 1. WHAT — 이 문서가 정하는 것

Platform sampler는 Jetson `tegrastats`, macOS `powermetrics`, Windows counters, external power meter처럼 platform-specific resource data를 수집하는 adapter다.

이 문서는 sampler를 EdgeEnv core runner에 직접 묶지 않고, optional resource evidence로 연결하는 기준을 정한다.

## 2. CONTENTS — 관련 파일과 기술 스택

현재 관련 파일:

- `inferedge_env/runners/local.py` — command 실행과 explicit JSON contract parsing
- `inferedge_env/result/schema.py` — optional `ResourceMetrics`
- `docs/resource-metrics-design.md` — resource metrics schema and policy
- `docs/local-runner-design.md` — local command contract
- `docs/sampler-failure-policy.md` — sampler failure와 benchmark success/failure policy
- `examples/scripts/emit_resource_metrics.py` — deterministic resource metrics smoke example
- `examples/scripts/run_with_sampler.py` — deterministic wrapper command sampler example

미래 구현 후보:

- `inferedge_env/samplers/` — optional sampler adapters
- `examples/scripts/` — sampler output을 `EDGEENV_RESOURCE_METRICS_JSON=`로 변환하는 examples

기술 스택: Python standard library process control, platform tools, JSON

## 3. HOW — 설계 방향

### Keep LocalRunner as command runner

`LocalRunner`는 지금처럼 benchmark command 실행과 stdout contract parsing만 담당한다.

Sampler process lifecycle을 core `LocalRunner` 안에 직접 넣지 않는다.

현재 책임:

```text
benchmark command
  stdout:
    EDGEENV_METRICS_JSON=...
    EDGEENV_RESOURCE_METRICS_JSON=...

LocalRunner
  parse explicit JSON lines
  build RunnerResult
```

### First integration path: wrapper command

v1.1의 가장 안전한 sampler 연결 방식은 wrapper command다.

```text
edgeenv bench run --config bench.yaml --target local.yaml
  -> BenchmarkConfig.command
       python examples/scripts/run_with_sampler.py -- python examples/scripts/emit_local_metrics.py
  -> wrapper starts sampler
  -> wrapper runs benchmark command
  -> wrapper summarizes sampler output
  -> wrapper prints EDGEENV_RESOURCE_METRICS_JSON=...
  -> wrapper prints EDGEENV_METRICS_JSON=...
```

이 방식에서는 EdgeEnv core가 sampler 권한, platform command, process cleanup을 직접 알 필요가 없다.

### Future integration path: sampler adapters

사용 패턴이 안정화되면 별도 adapter layer를 추가할 수 있다.

예상 interface:

```text
Sampler.start(context)
Sampler.stop()
Sampler.summary() -> ResourceMetrics
```

Adapter는 platform-specific tool을 감싸고, EdgeEnv core schema로 normalize한다.

초기 adapter 후보:

- Jetson: `tegrastats`
- macOS: `powermetrics`
- Windows: performance counters
- External meter: vendor CLI or file export

### Required metadata

Sampler output은 값뿐 아니라 source를 남겨야 한다.

최소 요구:

- metric value
- unit
- source
- sampling scope
- sampling interval if available
- benchmark window definition

현재 `ResourceMetrics.source`는 간단한 source marker다. 더 자세한 sampler metadata가 필요해지면 `env`나 future diagnostics field에 별도 schema를 설계한다.

## 4. HOW NOT — 피해야 할 함정

- `LocalRunner`가 platform tool을 직접 실행하게 만들지 않는다.
- `tegrastats`, `powermetrics`, Windows counters를 하나의 공통 값처럼 가정하지 않는다.
- permission이 필요한 sampler를 기본 path에 강제하지 않는다.
- host-wide idle power를 inference power처럼 기록하지 않는다.
- sampler failure를 성공 benchmark result로 조용히 숨기지 않는다.
- sampler output을 single composite score로 만들지 않는다.
- Docker/WSL/SSH target 구현과 sampler 구현을 한 PR에 섞지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Resource Metrics Design**: sampler output은 optional `resource_metrics` evidence로 저장한다.
- **Local Runner Design**: local runner는 explicit stdout contract만 읽는다.
- **Registry Resource Query Design**: sampler 값은 당분간 DB column이 아니라 `result.json` artifact에 남긴다.
- **Sampler Failure Policy**: sampler 실패만으로 primary benchmark result를 버리지 않는다.
- **Comparability**: sampler 값은 direct comparability gate가 아니다.

## 6. WHY — 배경 판단

Resource sampling은 platform마다 권한, sampling interval, 측정 범위가 다르다. 이를 너무 빨리 core runner에 넣으면 LocalRunner가 benchmark execution adapter를 넘어 platform manager가 된다.

EdgeEnv의 현재 강점은 "명시적 benchmark output을 검증하고 evidence bundle로 고정하는 것"이다. Sampler도 같은 철학을 따라야 한다. 먼저 wrapper command로 sampler output을 explicit JSON contract로 만들고, 반복되는 패턴이 확인되면 adapter layer를 설계한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Implementation Checklist

- [x] wrapper command example design
- [ ] sampler metadata schema decision
- [ ] Jetson `tegrastats` adapter design
- [ ] macOS `powermetrics` adapter design
- [ ] Windows counter adapter design
- [ ] external meter adapter design
- [x] sampler failure artifact policy

## Deferred Work

- Implementing platform samplers
- Adding sampler config fields
- Adding resource metric DB indexes
- Adding target-specific sampler presets
