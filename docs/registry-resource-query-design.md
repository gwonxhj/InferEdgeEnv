# Registry Resource Query Design

## 1. WHAT — 이 문서가 정하는 것

Resource metrics를 SQLite registry에 언제 넣을지, 언제까지 `result.json` artifact에서만 읽을지 기준을 정한다.

현재 정책은 단순하다. `runs.db`는 run 탐색용 summary index이고, resource metrics의 source of truth는 `.edgeenv/runs/<run_id>/result.json`이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/registry/db.py` — SQLite run summary index
- `inferedge_env/registry/models.py` — registry row model
- `inferedge_env/result/schema.py` — optional `ResourceMetrics`
- `inferedge_env/cli.py` — `runs show`가 `result_path`의 `result.json`을 읽어 resource metrics를 표시
- `docs/resource-metrics-design.md` — resource metrics contract

기술 스택: SQLite, JSON artifact, Pydantic

## 3. HOW — 현재 정책

### Keep resource metrics artifact-first

v1.1에서는 resource metrics를 DB column에 저장하지 않는다.

이유:

- resource metrics는 optional secondary evidence다.
- run마다 일부 field만 있을 수 있다.
- platform-specific sampler가 아직 없다.
- 지금 필요한 사용자 흐름은 `runs show <run_id>`에서 확인하는 정도다.

현재 흐름:

```text
runs.db row
  run_id
  created_at
  target/model/runtime/protocol/metrics summary
  result_path --------------+
                            |
                            v
                    result.json
                      resource_metrics
```

`runs list`는 빠른 registry summary만 보여준다. `runs show`는 `result_path`를 통해 `result.json`을 읽고, `resource_metrics`가 있을 때만 출력에 붙인다.

### Do not query resource metrics from SQLite yet

다음 기능은 아직 하지 않는다.

- `runs list`에서 power/memory column 표시
- `runs list --filter memory_peak_mb>...`
- `runs search --resource ...`
- resource metrics 기반 ranking
- resource metrics 기반 comparability gate

## 4. HOW NOT — 피해야 할 함정

- resource metrics 전체를 무조건 SQLite column으로 펼치지 않는다.
- unit 없는 `memory`, `power` 같은 column을 만들지 않는다.
- `result.json`과 `runs.db`가 서로 다른 값을 갖게 만들지 않는다.
- resource metrics가 없다는 이유로 old run을 migration 실패 상태로 만들지 않는다.
- memory/power/latency를 하나의 score로 만들지 않는다.

## 5. WHERE — migration이 필요해지는 신호

아래 조건이 생기면 registry migration 설계를 다시 연다.

- 사용자가 resource metrics로 run을 자주 필터링해야 한다.
- `runs list`에서 resource metrics summary를 빠르게 스캔해야 한다.
- run 수가 늘어나 `runs show`나 future report가 artifact 파일을 반복해서 여는 비용이 문제가 된다.
- platform-specific sampler가 안정화되어 공통적으로 채워지는 field가 생긴다.

그 전까지는 artifact-first 정책을 유지한다.

## 6. WHY — 배경 판단

SQLite registry는 local search index이고, result artifact는 evidence bundle이다. Resource metrics는 sampler와 target 환경에 따라 field 존재 여부와 의미가 달라질 수 있으므로, 너무 일찍 DB schema로 고정하면 migration 비용이 먼저 커진다.

EdgeEnv는 benchmark 결과를 더 빨리 줄 세우기보다, 어떤 evidence가 어떤 조건에서 기록됐는지 보존하는 쪽을 우선한다. 그래서 resource metrics query/index는 사용 패턴이 분명해질 때까지 늦춘다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Future Migration Shape

필요해지면 다음 원칙으로 migration한다.

- 기존 `runs` table은 그대로 유지한다.
- resource query 전용 table을 별도로 둔다.
- 각 row는 `run_id`, `metric_name`, `metric_value`, `unit`, `source`를 갖는다.
- `run_id`는 기존 `runs.run_id`와 연결한다.
- backfill은 `result_path`의 `result.json`을 읽어 수행한다.
- backfill 실패는 원본 run을 삭제하거나 invalid로 만들지 않는다.

예상 형태:

```text
resource_metric_index
  run_id
  metric_name      # memory_peak, power_mean, energy, temperature_peak
  metric_value
  unit             # mb, w, j, c
  source
```

이 migration은 query 기능이 실제로 필요할 때 별도 PR로 구현한다.
