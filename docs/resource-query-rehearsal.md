# Resource Query Rehearsal

## 1. WHAT — 이 문서가 정하는 것

`runs resources list`가 source registry와 imported registry에서 같은 lookup 의미를 유지하는지 확인한다.

검증 목표:

- local resource metrics run이 `resource_metric_index`에 조회된다.
- successful-run export/import 후 imported registry에서도 같은 run id, metric, value, unit, source로 조회된다.
- `runs show`의 `resource_metrics`가 canonical evidence이고, `resource_metric_index`는 rebuildable lookup index라는 경계를 유지한다.
- 조회 결과를 ranking, score, comparability gate로 해석하지 않는다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/registry/db.py` — `resource_metric_index` 생성, insert/import/backfill, lookup
- `inferedge_env/cli.py` — `runs resources list`
- `examples/benches/local_resource_metrics.yaml` — deterministic local resource metrics example
- `examples/scripts/emit_resource_metrics.py` — explicit metrics/resource metrics stdout contract
- `docs/registry-resource-query-design.md` — artifact-first + rebuildable query index 기준
- `docs/export-import-design.md` — successful-run evidence bundle portability 기준

기술 스택: LocalRunner, SQLite registry, successful-run export/import zip, `result.json`, Typer/Rich CLI

## 3. HOW — 리허설 절차

임시 root를 만든다.

```bash
work_root=$(mktemp -d /private/tmp/inferedge-resource-query-rehearsal.XXXXXX)
```

source registry에 resource metrics run을 만든다.

```bash
python -m inferedge_env.cli bench run \
  --target examples/profiles/local.yaml \
  --config examples/benches/local_resource_metrics.yaml \
  --edgeenv-root "$work_root/source.edgeenv"
```

source registry에서 resource lookup을 확인한다.

```bash
python -m inferedge_env.cli runs resources list \
  --metric memory_peak_mb \
  --min-value 500 \
  --edgeenv-root "$work_root/source.edgeenv"
```

successful-run evidence bundle을 export/import한다.

```bash
python -m inferedge_env.cli runs export <run_id> \
  --output "$work_root/run-resource.zip" \
  --edgeenv-root "$work_root/source.edgeenv"

python -m inferedge_env.cli runs import "$work_root/run-resource.zip" \
  --edgeenv-root "$work_root/imported.edgeenv"
```

imported registry에서 같은 lookup을 확인한다.

```bash
python -m inferedge_env.cli runs resources list \
  --metric memory_peak_mb \
  --min-value 500 \
  --edgeenv-root "$work_root/imported.edgeenv"
```

Expected behavior:

- source lookup and imported lookup return the same `run_id`.
- `memory_peak_mb=512.0 mb` remains visible in both registries.
- `Source: example-script` remains visible in both registries.
- `runs show <run_id>` on imported root still reads `result.json` and shows the full `resource_metrics` object.
- imported `runs.db` is rebuilt local index state, not zip evidence.

## 4. HOW NOT — 피해야 할 함정

- Do not compare resource query output as a regression result.
- Do not sort resource metrics as a leaderboard or ranking.
- Do not treat `resource_metric_index` as canonical evidence.
- Do not export `runs.db`; import must rebuild registry rows and lookup rows from artifacts.
- Do not add resource metrics to comparability required fields.
- Do not treat absent resource metrics as run failure or import failure.
- Do not commit generated `.edgeenv/`, zip bundles, stdout/stderr logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Registry Resource Query Design**: this validates the first query index shape on local and imported registries.
- **Export/Import Design**: this confirms successful-run import rebuilds lookup state from `result.json`.
- **Resource Metrics Design**: this keeps resource metrics optional and secondary.
- **Compare Workflow Guide**: this keeps resource lookup separate from comparability judgement.
- **V1 Handoff Status**: this closes the immediate next work item after resource query migration.

## 6. WHY — 배경 판단

Resource metrics are useful only if users can find the relevant run again. But they should not become a second source of truth or an accidental ranking surface. This rehearsal proves the intended middle ground: the registry can answer simple lookup questions, while the run artifact remains the evidence bundle.

Export/import is the important boundary. If the lookup index survives only because the original `runs.db` moved around, the design is wrong. The imported lookup must work because `result.json` was validated, copied, and re-indexed locally.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Resource query rehearsals should compare source and imported lookup outputs, not just confirm that a fresh local run can be queried.

## Validation Record — Local Export/Import

Status: passed.

Temporary root:

```text
/private/tmp/inferedge-resource-query-rehearsal.8kSnQn
```

Observed run:

```text
run-20260508-052016-46f39862
```

Source run command output:

```text
Benchmark run stored
Run ID: run-20260508-052016-46f39862
Result: /private/tmp/inferedge-resource-query-rehearsal.8kSnQn/source.edgeenv/runs/run-20260508-052016-46f39862/result.json
Latency mean: 12.8 ms
Resource metrics: stored (source=example-script, fields=energy_j, memory_mean_mb, memory_peak_mb, power_mean_w, power_peak_w, temperature_peak_c)
```

Source lookup output:

```text
EdgeEnv Resource Metrics
- Run ID: run-20260508-052016-46f39862
  Metric: memory_peak_mb=512.0 mb
  Source: example-script
```

Export/import output:

```text
Run evidence exported
Run ID: run-20260508-052016-46f39862
Archive: /private/tmp/inferedge-resource-query-rehearsal.8kSnQn/run-resource.zip

Run evidence imported
Run ID: run-20260508-052016-46f39862
Result: /private/tmp/inferedge-resource-query-rehearsal.8kSnQn/imported.edgeenv/runs/run-20260508-052016-46f39862/result.json
```

Imported lookup output:

```text
EdgeEnv Resource Metrics
- Run ID: run-20260508-052016-46f39862
  Metric: memory_peak_mb=512.0 mb
  Source: example-script
```

Imported source-filtered lookup output:

```text
EdgeEnv Resource Metrics
- Run ID: run-20260508-052016-46f39862
  Metric: power_peak_w=11.4 w
  Source: example-script
```

Imported `runs show` confirmed the canonical artifact still contains:

```json
{
  "resource_metrics": {
    "energy_j": 31.7,
    "memory_mean_mb": 420.5,
    "memory_peak_mb": 512.0,
    "power_mean_w": 8.2,
    "power_peak_w": 11.4,
    "source": "example-script",
    "temperature_peak_c": 72.0
  }
}
```

Conclusion:

- Source and imported registries returned the same run id for `memory_peak_mb >= 500`.
- Imported registry returned the same resource source after index rebuild.
- Full `resource_metrics` remained in imported `result.json`.
- The query index was useful for lookup, but did not replace artifacts or imply ranking/comparability semantics.
