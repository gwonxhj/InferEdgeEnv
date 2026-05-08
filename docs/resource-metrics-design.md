# Resource Metrics Design

## 1. WHAT — resource metrics가 하는 일

Resource metrics는 benchmark run의 latency/throughput 결과를 보조 설명하는 선택적 evidence다. 예시는 memory, power, energy, temperature처럼 target 환경에 강하게 묶이는 값이다.

이 설계의 목적은 richer metrics를 추가할 여지를 만들되, 기존 `edgeenv.result.v1` result JSON, SQLite registry, comparability checker contract를 깨뜨리지 않는 것이다.

## 2. CONTENTS — 대상 파일과 기술 스택

향후 구현 대상 파일:

- `inferedge_env/result/schema.py` — optional resource metrics schema
- `inferedge_env/runners/base.py` — runner result에 optional resource metrics 전달 경로
- `inferedge_env/runners/local.py` — explicit stdout contract parsing
- `inferedge_env/result/writer.py` — result JSON persistence
- `inferedge_env/compare/comparability.py` — comparability judgement가 resource metrics를 gate로 쓰지 않는지 검증
- `tests/` — schema, local parser, writer, compare regression tests
- `README.md`와 examples — 사용자-facing contract 문서화

기술 스택: Python standard library `json`, Pydantic, pytest

## 3. HOW — 구현 방향

### Compatibility first

기존 primary metrics contract는 그대로 유지한다.

```json
{
  "metrics": {
    "latency_mean_ms": 12.3,
    "latency_p50_ms": 12.0,
    "latency_p95_ms": 14.1,
    "latency_p99_ms": 15.0,
    "throughput_fps": 81.3
  }
}
```

Resource metrics는 required `metrics` object에 섞지 않고 optional top-level field로 둔다.

```json
{
  "resource_metrics": {
    "memory_peak_mb": 512.0,
    "memory_mean_mb": 420.5,
    "power_mean_w": 8.2,
    "power_peak_w": 11.4,
    "energy_j": 31.7,
    "temperature_peak_c": 72.0,
    "source": "benchmark-command"
  }
}
```

`resource_metrics`가 없던 기존 `result.json`은 계속 유효해야 한다. optional field 추가만으로 충분하다면 `schema_version`은 `edgeenv.result.v1`을 유지한다. 기존 reader가 unknown field를 거부하는 상황까지 지원해야 한다면 별도 migration 설계를 먼저 작성하고, 그 전에는 구현하지 않는다.

### Local runner stdout contract

`LocalRunner`는 primary metrics와 같은 방식으로 resource metrics도 explicit line만 신뢰한다.

```text
EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":512.0,"power_mean_w":8.2,"source":"benchmark-command"}
```

규칙:

- `EDGEENV_METRICS_JSON=`은 계속 필수다.
- `EDGEENV_RESOURCE_METRICS_JSON=`은 선택 사항이다.
- 여러 줄이 있으면 마지막으로 발견한 line만 사용한다.
- JSON object가 아니거나 schema validation에 실패하면 local run은 실패로 처리한다.
- stdout/stderr 전체는 기존 artifact writer가 그대로 저장한다.

### Proposed schema

초기 resource metrics는 모두 optional field로 둔다.

- `memory_peak_mb: float | None`
- `memory_mean_mb: float | None`
- `power_mean_w: float | None`
- `power_peak_w: float | None`
- `energy_j: float | None`
- `temperature_peak_c: float | None`
- `source: str | None`

값 이름에는 unit을 포함한다. unit 없는 `memory`, `power`, `temperature` 같은 이름은 쓰지 않는다.

### Registry policy

초기 구현에서는 SQLite registry column을 추가하지 않는다. `runs.db`는 성공 run의 탐색 index이고, richer evidence의 source of truth는 `.edgeenv/runs/<run_id>/result.json`이다.

`runs show`는 registry row의 `result_path`를 통해 `result.json`을 읽어 출력한다. `runs resources list`는 `runs.db`의 rebuildable `resource_metric_index`를 사용해 normalized resource metrics를 찾는다. 이 index는 local lookup용이며 `result.json`을 대체하지 않는다.

### CLI display policy

`bench run`은 resource metrics를 비교 점수처럼 해석하지 않고 저장 상태만 알려준다.

- `Resource metrics: omitted` — command가 `EDGEENV_RESOURCE_METRICS_JSON=` line을 내보내지 않았다.
- `Resource metrics: stored (...)` — schema-valid resource metrics가 `result.json`에 저장됐다.

`runs show`는 계속 JSON payload를 출력한다. Resource metrics가 있는 run만 `resource_metrics` object를 포함하고, 없는 run에는 field를 추가하지 않는다. 이 정책은 기존 `edgeenv.result.v1` artifact compatibility를 유지한다.

### Comparability policy

Resource metrics는 same-condition 필수 비교 필드에 포함하지 않는다.

필수 비교 필드는 계속 다음 항목이다.

- `model_hash`
- `input_shape`
- `input_dtype`
- `task`
- `precision`
- `batch_size`
- `warmup_runs`
- `repeat_runs`
- `include_preprocess`
- `include_postprocess`

Resource metrics는 비교 가능성 판단의 gate가 아니라 판단 이후의 secondary evidence다. 예를 들어 두 run이 `Comparable: Yes` 또는 `Comparable: Conditional`일 때 memory/power 차이를 보조 정보로 보여줄 수 있지만, resource metrics가 없다는 이유만으로 `Comparable: No`가 되면 안 된다.

## 4. HOW NOT — 피해야 할 함정

- Memory, power, latency를 하나의 composite score로 줄이지 않는다.
- Resource metrics를 same-condition comparability 필수 field로 추가하지 않는다.
- Platform-specific sampler를 core runner에 직접 묶지 않는다.
- Process startup overhead나 host-wide idle power를 inference power처럼 추정하지 않는다.
- Unit 없는 numeric field를 추가하지 않는다.
- Failed run diagnostic artifact를 성공 run의 resource evidence처럼 registry에 넣지 않는다.

## 5. WHERE — 기존 모듈과의 의존성

- **의존**: `RunnerResult`, `RunResult`, local runner stdout contract
- **피의존**: artifact writer, CLI `runs show`, report compare, README, tests
- **경계 / 어댑터**: target-specific sampler output과 EdgeEnv result evidence 사이의 adapter

영향 없어야 하는 contract:

- Primary `metrics` field는 required latency/throughput schema 유지
- `result.json` 기본 artifact 이름과 저장 위치 유지
- `.edgeenv/runs.db` registry layout 유지
- `report compare`의 required same-condition fields 유지

## 6. WHY — 배경 판단

Memory와 power는 edge inference에서 중요하지만, latency처럼 동일한 방식으로 항상 얻을 수 있는 값이 아니다. Jetson `tegrastats`, macOS `powermetrics`, Windows counters, external power meter는 sampling 범위와 권한, 측정 지점이 다르다.

그래서 EdgeEnv는 resource metrics를 "비교의 조건"이 아니라 "결과 해석을 돕는 evidence"로 다룬다. 이 경계가 있어야 richer metrics를 추가해도 기존 comparability checker가 과도한 판단을 하지 않는다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Implementation Checklist

- [x] `ResourceMetrics` Pydantic model 추가
- [x] `RunResult.resource_metrics` optional field 추가
- [x] `RunnerResult.resource_metrics` optional 전달 경로 추가
- [x] `LocalRunner`에서 `EDGEENV_RESOURCE_METRICS_JSON=` optional parser 추가
- [x] writer가 optional resource metrics를 `result.json`에 저장
- [x] `runs show` 출력 방식 결정: `result_path`의 result artifact를 읽어 표시한다.
- [x] `runs resources list`를 위한 rebuildable resource metric index 추가
- [x] `bench run` UX가 resource metrics 저장/생략 상태를 명시한다.
- [x] pytest:
  - missing resource metrics remains valid
  - valid resource metrics is persisted
  - invalid resource metrics fails local run
  - comparability result is unchanged by resource metrics presence or absence

## Deferred Work

- Platform-specific samplers; 기준은 [Platform Sampler Design](platform-sampler-design.md)을 따른다.
- Sampler failure handling; 기준은 [Sampler Failure Policy](sampler-failure-policy.md)을 따른다.
- Richer resource query/report UX; 기준은 [Registry Resource Query Design](registry-resource-query-design.md)을 따른다.
