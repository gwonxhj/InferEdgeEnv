# Registry Resource Query Design

## 1. WHAT — 이 문서가 정하는 것

Resource metrics를 SQLite registry에서 어떻게 조회할지, 그리고 `result.json` artifact source-of-truth를 어떻게 유지할지 기준을 정한다.

현재 정책은 artifact-first + query index다. `runs.db`는 run 탐색용 summary index이고, resource metrics의 source of truth는 `.edgeenv/runs/<run_id>/result.json`이다. SQLite의 `resource_metric_index` table은 조회 편의를 위한 rebuildable index일 뿐 canonical evidence가 아니다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/registry/db.py` — SQLite run summary index and resource metric lookup index
- `inferedge_env/registry/models.py` — registry row and resource metric row models
- `inferedge_env/result/schema.py` — optional `ResourceMetrics`
- `inferedge_env/cli.py` — `runs show`가 `result.json`을 읽고, `runs resources list`가 query index를 표시
- `docs/resource-metrics-design.md` — resource metrics contract
- `docs/export-import-design.md` — import 시 registry row를 artifact에서 rebuild하는 portability policy

기술 스택: SQLite, JSON artifact, Pydantic, Typer/Rich CLI

## 3. HOW — 현재 정책

### Keep resource metrics artifact-first, but add a rebuildable query index

Resource metrics는 `runs` table column으로 펼치지 않는다. 대신 별도 table인 `resource_metric_index`를 둔다.

이유:

- resource metrics는 optional secondary evidence다.
- run마다 일부 field만 있을 수 있다.
- sampler/source마다 field 의미와 sampling window가 다를 수 있다.
- `result.json`과 `runs.db`가 다른 값을 갖는 것을 피해야 한다.
- 사용자가 memory/power/temperature evidence가 있는 run을 빠르게 찾는 흐름은 생겼다.

현재 흐름:

```text
runs.db row
  run_id
  created_at
  target/model/runtime/protocol/metrics summary
  result_path --------------+
                            |
                            v
                    result.json  # source of truth
                      resource_metrics
                            |
                            v
                    resource_metric_index  # rebuildable local query index
```

`runs list`는 빠른 registry summary만 보여준다. `runs show`는 `result_path`를 통해 `result.json`을 읽고, `resource_metrics`가 있을 때만 출력에 붙인다. `runs resources list`는 `resource_metric_index`를 읽어 resource metric rows를 표시한다.

### Query command

Supported first command:

```bash
edgeenv runs resources list
edgeenv runs resources list --metric memory_peak_mb
edgeenv runs resources list --metric power_peak_w --min-value 8 --source jetson-tegrastats
```

The output is inspection-oriented, not ranking-oriented. It lists run id, metric name, value, unit, and source. Full run context remains available through:

```bash
edgeenv runs show <run_id>
```

### Indexed fields

The first index supports normalized numeric fields from `ResourceMetrics`:

| Metric name | Unit |
| --- | --- |
| `memory_peak_mb` | `mb` |
| `memory_mean_mb` | `mb` |
| `power_mean_w` | `w` |
| `power_peak_w` | `w` |
| `energy_j` | `j` |
| `temperature_peak_c` | `c` |

`source` is copied to each indexed row when present. Unknown fields remain rejected by the Pydantic `ResourceMetrics` schema before they can be written to `result.json`.

### Migration and backfill

`RunRegistry.initialize()` creates `resource_metric_index` if it is missing. New successful runs and imported successful runs call `RunRegistry.insert()`, which rebuilds index rows from the `RunResult` object.

For an existing `runs.db`, initialization also backfills missing index rows by reading each run's `result_path` and loading `result.json`. Backfill failures do not delete runs or mark them invalid; they only skip index rows for unreadable artifacts.

The table shape is:

```text
resource_metric_index
  run_id
  metric_name
  metric_value
  unit
  source
```

The primary key is `(run_id, metric_name)`. This assumes a single normalized value per metric per run, which matches `edgeenv.result.v1`.

### Still out of scope

The migration intentionally does not add:

- resource metric columns directly on `runs`
- default resource metric columns in `runs list`
- `runs search --resource ...`
- resource metrics 기반 ranking
- resource metrics 기반 comparability gate
- composite memory/power/latency score

## 4. HOW NOT — 피해야 할 함정

- resource metrics 전체를 무조건 SQLite column으로 펼치지 않는다.
- unit 없는 `memory`, `power` 같은 column을 만들지 않는다.
- `result.json`과 `runs.db`가 서로 다른 값을 갖게 만들지 않는다.
- resource metrics가 없다는 이유로 old run을 migration 실패 상태로 만들지 않는다.
- memory/power/latency를 하나의 score로 만들지 않는다.
- `runs resources list` 결과 순서를 metric value 순위처럼 만들지 않는다.

## 5. WHERE — future migration이 필요해지는 신호

아래 조건이 생기면 다음 단계 registry migration 설계를 다시 연다.

- run 수가 늘어나 `runs show`나 future report가 artifact 파일을 반복해서 여는 비용이 문제가 된다.
- 특정 report가 source별 resource metrics summary를 반복해서 계산해야 한다.
- `runs resources list`의 단순 필터로는 충분하지 않은 query use case가 생긴다.
- platform-specific sampler가 안정화되어 metadata-aware query가 필요해진다.

그 전까지는 현재 table을 rebuildable local index로 유지한다.

## 6. WHY — 배경 판단

SQLite registry는 local search index이고, result artifact는 evidence bundle이다. Resource metrics는 sampler와 target 환경에 따라 field 존재 여부와 의미가 달라질 수 있으므로, `runs` table schema로 고정하지 않고 query 전용 table로 분리한다.

EdgeEnv는 benchmark 결과를 더 빨리 줄 세우기보다, 어떤 evidence가 어떤 조건에서 기록됐는지 보존하는 쪽을 우선한다. 그래서 resource metrics query는 run을 찾는 데만 쓰고, compare judgement나 ranking으로 승격하지 않는다.

같은 이유로 export/import 설계에서도 `runs.db`는 archive에 넣는 canonical evidence가 아니라 import 후 `result.json`에서 다시 만들 수 있는 local index로 취급한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Implemented Migration Shape

Implemented first migration:

- 기존 `runs` table은 그대로 유지한다.
- resource query 전용 table을 별도로 둔다.
- 각 row는 `run_id`, `metric_name`, `metric_value`, `unit`, `source`를 갖는다.
- `run_id`는 기존 `runs.run_id`와 연결한다.
- insert/import는 `RunResult.resource_metrics`에서 index row를 만든다.
- backfill은 `result_path`의 `result.json`을 읽어 수행한다.
- backfill 실패는 원본 run을 삭제하거나 invalid로 만들지 않는다.

Validation:

```bash
python -m pytest tests/test_registry.py tests/test_cli.py -q
python -m inferedge_env.cli runs resources list --help
```
