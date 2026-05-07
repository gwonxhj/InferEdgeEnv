# Sampler Metadata Artifact Policy

## 1. WHAT — 이 문서가 정하는 것

future sampler adapter가 만든 metadata와 raw sampler output을 성공 run artifact 안에 어디에 저장할지 결정한다.

결정: sampler metadata의 canonical 위치는 `.edgeenv/runs/<run_id>/sampler/metadata.json`이다. Raw sampler output은 같은 `sampler/` directory 아래에 sampler별 파일로 둔다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/result/writer.py` — sampler artifact writer helper and future integration point
- `inferedge_env/result/schema.py` — `RunResult.resource_metrics` remains normalized summary only
- `inferedge_env/samplers/base.py` — `SamplerSummary.metadata`, `SamplerSummary.raw_artifacts`
- `inferedge_env/samplers/jetson_tegrastats.py` — first adapter metadata/raw artifact producer
- `docs/sampler-adapter-api-design.md` — adapter API and metadata schema
- `docs/export-import-design.md` — portable evidence bundle contract
- `docs/resource-metrics-design.md` — optional resource metrics policy

기술 스택: JSON artifact, local filesystem, export/import manifest checksums

## 3. HOW — storage decision

### Chosen layout

Future successful runs with sampler adapter evidence should use:

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

`metadata.json` is the canonical sampler metadata artifact. Raw files listed in `metadata.json.raw_artifacts` must be relative to the run directory.

### Why not `RunResult.env["sampler"]`

`RunResult.env` is useful for compact process/environment facts, but sampler metadata can grow with raw artifact references, tool details, field mappings, warnings, and sample counts. Putting that into `result.json` would make result schema consumers parse platform diagnostics even when they only need benchmark outcome.

Policy:

- Keep `result.json` focused on benchmark identity, protocol, primary metrics, and optional normalized `resource_metrics`.
- Do not put raw sampler lines or platform-specific field maps into `RunResult.env["sampler"]`.
- At most, future `RunResult.env` may include a small pointer such as `"sampler_metadata_path": "sampler/metadata.json"` if a reader needs discovery without scanning files.

### Why not `env.json`

`env.json` captures environment facts for the run. Sampler metadata is measurement evidence, not just environment. It also needs raw artifact references and sampling window details that belong with sampler evidence.

Policy:

- Keep `env.json` for system/runtime environment capture.
- Do not overload `env.json` with sampler lifecycle or raw sample summaries.
- If sampler availability checks are useful environment facts, record them in `sampler/metadata.json.warnings` or future metadata fields instead.

### Metadata shape

`sampler/metadata.json` must use:

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
    }
  },
  "warnings": []
}
```

Required keys:

- `schema_version`
- `sampler_name`
- `platform_tool`
- `sampling_scope`
- `benchmark_window`
- `sample_count`
- `raw_artifacts`
- `fields`
- `warnings`

### Writer behavior

`inferedge_env/result/writer.py` provides `write_sampler_artifacts(run_dir, sampler_summary)` to persist the metadata artifact. Future runner integration should call this only after a successful primary benchmark result is available.

Expected behavior:

- If `SamplerSummary.resource_metrics` is present, persist it in `result.json.resource_metrics`.
- If `SamplerSummary.metadata` is present, write `.edgeenv/runs/<run_id>/sampler/metadata.json`.
- If `SamplerSummary.raw_artifacts` is present, ensure raw files live under `.edgeenv/runs/<run_id>/sampler/`.
- Reject unsafe raw artifact references such as absolute paths, `..`, or files outside `sampler/`.
- If sampler failed recoverably, write metadata with warnings and `sample_count: 0` only if adapter integration has enough context to make that useful.
- Do not create `.edgeenv/failed-runs/` only because optional sampler metadata is absent.

### Export/import policy

Current export/import requires the six core successful-run files:

- `result.json`
- `config.yaml`
- `target.yaml`
- `env.json`
- `stdout.log`
- `stderr.log`

Sampler artifacts should be optional extension evidence in a future portability update:

```text
<run_id>/
  manifest.json
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

Manifest rules for that future update:

- `sampler/metadata.json` is optional but, if present, must be checksummed.
- Every raw file listed in `sampler/metadata.json.raw_artifacts` must appear in the manifest.
- Import must reject `sampler/` entries with unsafe paths, symlinks, duplicate names, or paths outside the top-level run directory.
- Import must copy sampler artifacts before rebuilding registry, but registry rows still come from `result.json`.
- Import must not require sampler artifacts for older bundles.

### CLI display policy

`runs show` should keep showing normalized `resource_metrics` from `result.json`.

Future CLI additions can expose metadata explicitly:

```bash
edgeenv runs show <run_id>
edgeenv runs sampler show <run_id>
```

Do not add verbose sampler metadata to default `runs list`.

## 4. HOW NOT — 피해야 할 함정

- Do not store sampler metadata only in `result.json`.
- Do not store raw sampler logs in `env.json`.
- Do not make `sampler/metadata.json` required for all successful run bundles.
- Do not export sampler raw files without checksum and path safety validation.
- Do not let sampler metadata change comparability mode.
- Do not treat board-level power metadata as model-only measurement.
- Do not wire sampler metadata persistence into failed-run registry behavior.

## 5. WHERE — 다른 설계와의 관계

- **Sampler Adapter API Design**: `SamplerSummary.metadata` maps directly to `sampler/metadata.json`.
- **Resource Metrics Design**: `result.json.resource_metrics` remains the normalized summary.
- **Export/Import Design**: sampler artifacts require a future optional manifest extension.
- **Registry Resource Query Design**: DB columns are still deferred; metadata is artifact-first.
- **Failed Run Inspection**: failed-run artifacts stay separate and should not be compared as successful sampler evidence.

## 6. WHY — 배경 판단

Sampler evidence has two audiences. Most users need normalized `resource_metrics` near the benchmark result. Reviewers and future debugging tools need metadata, raw sample references, sample count, and warnings.

Putting everything into `result.json` would make the stable result contract noisy and platform-specific. Putting everything into `env.json` would blur environment capture with measurement evidence. A dedicated `sampler/metadata.json` keeps the evidence discoverable, portable, and optional.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Sampler metadata should be optional extension evidence so old successful-run bundles remain importable.
