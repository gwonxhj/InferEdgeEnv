# LocalRunner Sampler Wiring Design

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

`LocalRunner`가 future sampler adapter lifecycle을 어떻게 연결할지 결정한다. 목표는 platform sampler를 붙이더라도 기존 local command contract인 `EDGEENV_METRICS_JSON=`와 `EDGEENV_RESOURCE_METRICS_JSON=`를 깨뜨리지 않는 것이다.

결정: sampler adapter는 optional target/profile capability로 enable한다. `LocalRunner`는 benchmark command 실행 전후에 adapter lifecycle만 관리하고, primary benchmark metrics는 계속 stdout의 `EDGEENV_METRICS_JSON=`에서만 읽는다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/runners/local.py` — future sampler lifecycle orchestration point
- `inferedge_env/samplers/base.py` — `SamplerContext`, `SamplerSummary`, failure taxonomy
- `inferedge_env/samplers/jetson_tegrastats.py` — first platform sampler adapter
- `inferedge_env/result/writer.py` — `write_sampler_artifacts`
- `inferedge_env/result/exporter.py` — optional sampler evidence portability
- `inferedge_env/config/target_profile.py` — recommended sampler enable surface
- `docs/local-runner-design.md` — explicit stdout metrics contract
- `docs/sampler-adapter-api-design.md` — adapter lifecycle and metadata schema
- `docs/sampler-failure-policy.md` — preserve/omit/fail policy
- `docs/sampler-metadata-artifact-policy.md` — metadata/raw artifact layout

기술 스택: Python subprocess orchestration, optional target profile config, sampler adapter protocol, JSON artifacts

## 3. HOW — wiring contract

### Enable surface

Recommended first implementation: add optional sampler settings to target profile, not benchmark config.

```yaml
target_name: jetson-nano-local
target_type: local
board_name: Jetson Nano
os: Ubuntu 22.04
runtime_tags:
  - jetson
sampler:
  name: jetson-tegrastats
  required: false
  interval_ms: 500
  startup_wait_ms: 600
  raw_log: true
```

Reason:

- sampler availability is target/platform capability, not model protocol
- existing benchmark configs remain portable and valid
- Jetson-specific fields stay out of generic benchmark schema
- a local run without `sampler` behaves exactly like current `LocalRunner`

Do not make sampler config required for `target_type: local`.

### Lifecycle

Future `LocalRunner` orchestration should use this sequence:

```text
run_id is allocated before command execution
run_dir is reserved or a sampler staging directory is created
sampler = build_sampler(target.sampler)
context = SamplerContext(run_id, benchmark_name, target_name, target_type, argv, run_dir)
sampler.start(context)
try:
  execute benchmark command with shell=False
finally:
  sampler.stop()
parse EDGEENV_METRICS_JSON= from benchmark stdout
parse EDGEENV_RESOURCE_METRICS_JSON= from benchmark stdout if present
summary = sampler.summary()
resolve resource metrics precedence
write successful run core artifacts
write sampler metadata/raw artifacts
insert registry row
```

The `finally` cleanup is mandatory. Sampler cleanup must run on benchmark command failure, timeout, invalid metrics, and success.

### Artifact write timing

Successful benchmark:

```text
.edgeenv/runs/<run_id>/
  result.json
  config.yaml
  target.yaml
  env.json
  stdout.log
  stderr.log
  sampler/
    metadata.json
    tegrastats.log
```

Timing rules:

- Allocate `run_id` before sampler start so raw artifact paths can be stable.
- Start sampler before the benchmark command.
- Stop sampler after the benchmark command exits or times out.
- Build `RunResult` only after primary metrics are validated.
- Persist `SamplerSummary.resource_metrics` into `result.json.resource_metrics` only after precedence is resolved.
- Call `write_sampler_artifacts(run_dir, summary)` only after the successful run directory exists.
- Insert the registry row only after core artifacts and sampler artifacts are written successfully.

Failed primary benchmark:

- Preserve failed-run artifact under `.edgeenv/failed-runs/<run_id>/`.
- Do not insert registry row.
- Do not write sampler evidence into `.edgeenv/runs/<run_id>/`.
- Future failed-run diagnostics may include sampler warnings only after a separate failed-run sampler artifact policy.

### Resource metrics precedence

There are two possible resource evidence sources:

- benchmark command stdout: `EDGEENV_RESOURCE_METRICS_JSON=`
- sampler adapter: `SamplerSummary.resource_metrics`

Precedence decision:

1. If sampler adapter is enabled and produces valid `ResourceMetrics`, use sampler adapter resource metrics.
2. If sampler adapter is enabled but recoverably unavailable or unparseable, fall back to valid `EDGEENV_RESOURCE_METRICS_JSON=` only when the benchmark command emitted it.
3. If sampler adapter is not enabled, preserve current behavior and use only `EDGEENV_RESOURCE_METRICS_JSON=`.
4. If both sources exist, record the chosen source in `ResourceMetrics.source`; do not merge fields from both sources in v1.

Why no merge: command-emitted metrics and platform sampler metrics can have different sampling windows and units. Merging would make evidence look more precise than it is.

### Failure policy

Primary benchmark failure always wins:

- non-zero command exit
- command timeout
- missing `EDGEENV_METRICS_JSON=`
- invalid primary metrics JSON/schema

These cases create failed-run artifacts and do not create registry rows.

Recoverable sampler failures:

- unavailable tool
- permission denied
- no samples
- unparseable output
- stop timeout after benchmark command completed

If `required: false`, preserve the successful primary benchmark and omit sampler-derived resource metrics. If useful metadata is available, write `sampler/metadata.json` with warnings and `sample_count: 0`.

Fatal sampler failures:

- `required: true` start failure
- invalid sampler-generated `ResourceMetrics`
- raw artifact write failure when raw evidence is required

If `required: true`, fail the run and create failed-run artifact. If `required: false`, prefer preserving the benchmark run without sampler resource metrics unless emitted evidence is corrupt.

### stdout contract compatibility

`LocalRunner` must continue to parse:

```text
EDGEENV_METRICS_JSON={...}
EDGEENV_RESOURCE_METRICS_JSON={...}
```

Rules:

- `EDGEENV_METRICS_JSON=` remains the only source of primary latency/throughput metrics.
- Sampler adapters never generate or modify primary benchmark metrics.
- Existing wrapper commands keep working.
- Existing configs/profiles without sampler fields keep validating and running.
- Malformed `EDGEENV_RESOURCE_METRICS_JSON=` still fails the run when emitted, because EdgeEnv cannot trust corrupt evidence.

### CLI UX

Initial CLI should avoid adding a verbose sampler panel to default output.

Recommended success messages:

```text
Resource metrics: stored (source=jetson-tegrastats, fields=memory_peak_mb, power_mean_w)
Sampler metadata: stored (.edgeenv/runs/<run_id>/sampler/metadata.json)
```

or:

```text
Resource metrics: omitted
Sampler metadata: stored with warnings (.edgeenv/runs/<run_id>/sampler/metadata.json)
```

Do not add sampler metadata to `runs list`. Detailed inspection uses:

```bash
edgeenv runs sampler show <run_id>
```

## 4. HOW NOT — 피해야 할 함정

- Do not replace `EDGEENV_METRICS_JSON=` with sampler-generated primary metrics.
- Do not merge command resource metrics and sampler resource metrics field-by-field in v1.
- Do not make sampler config required for all local profiles.
- Do not store sampler metadata in `result.json` or `env.json`.
- Do not insert registry rows before sampler artifacts have been written for a successful sampled run.
- Do not write successful sampler evidence under `.edgeenv/runs/` for a failed primary benchmark.
- Do not add resource metrics or sampler source to comparability gates.
- Do not include SSH, WSL, Docker, or cloud target behavior in this wiring.

## 5. WHERE — 다른 설계와의 관계

- **Local Runner Design**: preserves explicit stdout contract and failed-run artifact behavior.
- **Sampler Adapter API Design**: uses `SamplerContext`, `SamplerSummary`, and typed sampler errors.
- **Sampler Failure Policy**: maps sampler failures to preserve/omit/fail behavior.
- **Sampler Metadata Artifact Policy**: stores metadata under `sampler/metadata.json`.
- **Export/Import Design**: sampler artifacts are portable optional evidence once written.
- **Registry Resource Query Design**: sampler metadata remains artifact-first; normalized resource values use a rebuildable lookup index.
- **Comparability**: sampler evidence remains secondary and does not change compare mode.

## 6. WHY — 배경 판단

The risky version of sampler integration would make `LocalRunner` infer benchmark metrics from platform tools or silently combine unrelated evidence sources. That would blur EdgeEnv's main contract: benchmark commands declare primary metrics, EdgeEnv validates and preserves evidence.

Target-profile sampler enablement keeps platform concerns near the target, leaves benchmark configs portable, and gives Jetson users a clean path without making every local run platform-aware.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Sampler wiring must preserve existing wrapper commands because they are the current proven integration path.

## Implementation Checklist

- [x] Add optional sampler schema to target profile.
- [x] Add sampler factory for `jetson-tegrastats`.
- [x] Allocate run id before local command execution.
- [x] Start/stop sampler around command execution with mandatory cleanup.
- [x] Preserve `EDGEENV_METRICS_JSON=` as the only primary metrics source.
- [x] Resolve resource metrics precedence without merging sources.
- [x] Write sampler metadata/raw artifacts only for successful runs.
- [x] Export/import sampled runs using existing optional sampler artifact support.
- [x] Add tests for disabled sampler preserving current local runner behavior.
- [x] Add tests for recoverable sampler failure preserving successful primary run.
- [x] Add tests for required sampler failure creating failed-run artifact.
- [x] Add tests for both resource metrics sources choosing sampler source.
- [x] Add explicit sampler metadata inspection through `runs sampler show <run_id>`.
