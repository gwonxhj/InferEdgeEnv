# Sampler Adapter API Design

## 1. WHAT — 이 문서가 정하는 것

`inferedge_env/samplers/`에 future platform sampler adapter를 추가할 때 사용할 최소 API, lifecycle, metadata schema, failure taxonomy를 정한다.

이 문서는 구현 PR이 아니라 API 설계 기준이다. Jetson `tegrastats` wrapper 실측 결과를 바탕으로 하되, `LocalRunner`에 platform lifecycle을 직접 넣지 않는 현재 경계를 유지한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `docs/platform-sampler-design.md` — wrapper-first sampler integration boundary
- `docs/jetson-tegrastats-wrapper.md` — Jetson `tegrastats` 실측 wrapper validation
- `docs/resource-metrics-design.md` — optional `ResourceMetrics` schema and policy
- `docs/sampler-failure-policy.md` — sampler failure가 benchmark success/failure에 미치는 영향
- `docs/local-runner-design.md` — `LocalRunner`는 explicit stdout contract만 처리한다는 기준
- `inferedge_env/result/schema.py` — current `ResourceMetrics`
- future `inferedge_env/samplers/` — adapter interfaces and implementations

기술 스택: Python standard library process control, dataclasses or Pydantic for internal contracts, platform command adapters, JSON-serializable metadata

## 3. HOW — proposed adapter contract

### Design goal

Sampler adapter는 benchmark command window 바깥에서 resource evidence를 수집하고, EdgeEnv의 normalized result evidence로 요약한다.

Adapter가 해야 하는 일:

- platform tool availability 확인
- sampler process/file/session lifecycle 관리
- raw samples 수집
- normalized `ResourceMetrics` 산출
- sampling metadata 산출
- recoverable failure를 명확히 보고

Adapter가 하지 말아야 하는 일:

- benchmark command 실행
- primary latency/throughput metrics 생성
- `LocalRunner`의 stdout contract parsing 대체
- comparability mode 결정
- model/dataset artifact 관리

### Core interface

Proposed minimal interface:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from inferedge_env.result.schema import ResourceMetrics


@dataclass(frozen=True)
class SamplerContext:
    run_id: str
    benchmark_name: str
    target_name: str
    target_type: str
    command: list[str]
    artifact_dir: Path
    monotonic_start_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SamplerSummary:
    resource_metrics: ResourceMetrics | None
    metadata: dict[str, Any]
    raw_artifacts: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class Sampler(Protocol):
    name: str

    def start(self, context: SamplerContext) -> None:
        ...

    def stop(self) -> None:
        ...

    def summary(self) -> SamplerSummary:
        ...
```

Lifecycle rule:

```text
context = SamplerContext(...)
sampler.start(context)
try:
    run benchmark command
finally:
    sampler.stop()
summary = sampler.summary()
```

The `finally` block is mandatory. Adapter cleanup must run even if the benchmark command fails or times out.

### Metadata schema

`ResourceMetrics` stays small and normalized:

```json
{
  "memory_mean_mb": 881.0,
  "memory_peak_mb": 881.0,
  "power_mean_w": 4.482,
  "power_peak_w": 4.482,
  "temperature_peak_c": 38.343,
  "source": "jetson-tegrastats"
}
```

Sampler metadata should be separate from `ResourceMetrics`. First implementation should store it in `RunResult.env["sampler"]` or a future explicit diagnostics artifact, not by adding broad fields to `ResourceMetrics`.

Proposed metadata shape:

```json
{
  "schema_version": "edgeenv.sampler-metadata.v1",
  "sampler_name": "jetson-tegrastats",
  "sampler_version": "0.1",
  "platform_tool": "tegrastats",
  "platform_tool_path": "/usr/bin/tegrastats",
  "platform_tool_version": null,
  "sampling_interval_ms": 500,
  "startup_wait_ms": 600,
  "sampling_scope": "host",
  "benchmark_window": "sampler-start-before-command-stop-after-command",
  "sample_count": 1,
  "raw_artifacts": [
    "sampler/tegrastats.log"
  ],
  "fields": {
    "memory_mean_mb": {
      "source_field": "RAM used",
      "unit": "MB",
      "aggregation": "mean"
    },
    "power_mean_w": {
      "source_field": "VDD_IN average",
      "unit": "W",
      "aggregation": "mean"
    }
  },
  "warnings": []
}
```

Required metadata fields:

- `schema_version`
- `sampler_name`
- `platform_tool`
- `sampling_scope`
- `benchmark_window`
- `sample_count`
- `fields`

Recommended fields:

- `platform_tool_path`
- `platform_tool_version`
- `sampling_interval_ms`
- `startup_wait_ms`
- `raw_artifacts`
- `warnings`

### Raw artifact policy

Sampler raw output is useful evidence, but it should not be mixed into `stdout.log` as the only source of truth once adapters exist.

Recommended layout for a future adapter run:

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

This is a layout extension, not a `result.json` schema break. Export/import must include sampler artifacts only after a separate portability update.

### Jetson tegrastats adapter mapping

The validated wrapper saw Jetson `tegrastats` lines like:

```text
RAM 848/7620MB ... cpu@35.593C gpu@36.437C ... VDD_IN 4408mW/4408mW
```

Mapping:

- `RAM used` -> `memory_mean_mb`, `memory_peak_mb`
- `VDD_IN instant` -> `power_peak_w`
- `VDD_IN average` or instant fallback -> `power_mean_w`
- all `*@...C` temperatures -> `temperature_peak_c`
- `source` -> `jetson-tegrastats`

Important interpretation:

- `VDD_IN` is board/input power evidence, not model-only energy.
- temperature is peak observed platform sensor temperature, not model temperature.
- short benchmark windows may have low sample count; metadata must reveal `sample_count`.

### Failure taxonomy

Adapter errors should be typed so the caller can decide whether to preserve the primary benchmark.

Recoverable sampler failures:

- `SamplerUnavailable`: platform tool missing
- `SamplerPermissionDenied`: tool exists but cannot run with current permissions
- `SamplerNoSamples`: process started but no samples were captured
- `SamplerUnparseableOutput`: samples existed but no supported fields were parseable
- `SamplerStopTimeout`: cleanup required kill/force stop but benchmark command completed

Fatal sampler failures:

- `SamplerStartFailedRequired`: caller explicitly required sampler and it could not start
- `SamplerCorruptResourceMetrics`: adapter generated invalid `ResourceMetrics`
- `SamplerRawArtifactWriteFailed`: raw sampler evidence could not be written when adapter mode requires raw evidence

Policy:

- Recoverable sampler failures produce a successful benchmark run without `resource_metrics`, plus warning metadata when metadata storage exists.
- Fatal sampler failures fail the run only when the user explicitly requested required sampling or when emitted evidence would be invalid.
- Benchmark command failure still wins: failed primary benchmark creates failed-run artifact regardless of sampler state.

### Config shape for future implementation

Do not add this to `BenchmarkConfig` until implementation work starts. Candidate shape:

```yaml
sampler:
  name: jetson-tegrastats
  required: false
  interval_ms: 500
  startup_wait_ms: 600
  raw_log: true
```

This should remain optional and target-aware. Existing configs without `sampler` must continue to validate and behave exactly as they do now.

## 4. HOW NOT — 피해야 할 함정

- Do not put sampler process lifecycle inside `LocalRunner` without an adapter boundary.
- Do not make sampler config required for `target_type: local`.
- Do not add resource metrics to comparability required fields.
- Do not store platform-specific raw samples only inside `result.json`.
- Do not silently overwrite benchmark command `EDGEENV_RESOURCE_METRICS_JSON=` without a clear precedence policy.
- Do not claim board-level power is model-only power.
- Do not add SSH, Docker, WSL, or cloud target execution as part of sampler adapter work.
- Do not bump `edgeenv.result.v1` unless result schema fields actually change.

## 5. WHERE — 다른 설계와의 관계

- **Jetson Tegrastats Wrapper Guide**: provides the first proven sampler lifecycle and field mapping.
- **Resource Metrics Design**: normalized resource metrics remain optional evidence.
- **Sampler Failure Policy**: failure taxonomy maps to preserve/omit/fail behavior.
- **Local Runner Design**: adapter work must not blur local command responsibility.
- **Export/Import Design**: sampler raw artifacts need a future portability update before becoming export evidence.
- **Registry Resource Query Design**: sampler metadata and resource values remain artifact-first until query use cases are clear.

## 6. WHY — 배경 판단

The Jetson wrapper proved that real platform sampling can fit EdgeEnv's explicit evidence contract without making `LocalRunner` a platform manager. The next risk is adding an adapter too loosely and then discovering that metadata, raw artifacts, and failure behavior are inconsistent across platforms.

This design keeps the first adapter API small: start, stop, summarize. It also makes metadata explicit enough to explain what a resource number means without turning resource metrics into ranking or comparability gates.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Short benchmark windows can produce only one or zero sampler samples; adapter metadata must expose sample count and timing window.
- `tegrastats` `VDD_IN` should be documented as board/input power evidence, not model-only power.

## Implementation Checklist

- [x] Add `inferedge_env/samplers/base.py` with `SamplerContext`, `SamplerSummary`, `Sampler` protocol, and failure classes.
- [x] Add `inferedge_env/samplers/jetson_tegrastats.py` parser and process adapter.
- [ ] Keep `examples/scripts/run_with_tegrastats.py` as the user-facing wrapper even after adapter code lands.
- [ ] Decide whether sampler metadata first lives in `env.json`, `RunResult.env["sampler"]`, or `.edgeenv/runs/<run_id>/sampler/metadata.json`.
- [x] Add tests for unavailable tool, no samples, parser success, process summary, and required sampler failure.
- [ ] Update export/import design if sampler raw artifacts become part of portable evidence bundles.
