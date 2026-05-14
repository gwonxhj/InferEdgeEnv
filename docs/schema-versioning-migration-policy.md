# Schema Versioning And Migration Policy

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This policy defines how InferEdgeEnv keeps evidence artifacts interpretable across releases: `result.json`, `failure.json`, `sampler/metadata.json`, export `manifest.json`, and the local SQLite registry.

The policy is intentionally conservative. Current `v1` evidence remains supported, while unknown future schemas are not imported automatically. Accepting a new schema requires an explicit migration design and tests first.

## 2. CONTENTS — Files And Stack

Related files:

- `inferedge_env/result/schema.py` — successful run `RunResult` schema and `edgeenv.result.v1`
- `inferedge_env/result/writer.py` — successful/failed run artifact writer and sampler metadata writer
- `inferedge_env/result/exporter.py` — export/import manifest validation, checksum validation, safe extraction
- `inferedge_env/samplers/base.py` — `edgeenv.sampler-metadata.v1`
- `inferedge_env/registry/db.py` — rebuildable local SQLite index
- `tests/test_result_writer.py` — schema version presence, legacy default, future-version rejection tests
- `docs/export-import-design.md` — bundle path safety, checksum, and manifest validation
- `docs/sampler-metadata-artifact-policy.md` — sampler metadata artifact shape

Stack: Pydantic, JSON artifacts, zip manifest, SHA-256 checksums, SQLite local index

## 3. HOW — Version Compatibility Policy

### Current Schema Markers

| Artifact | Canonical location | Current marker | Compatibility rule |
|---|---|---:|---|
| Successful run result | `.edgeenv/runs/<run_id>/result.json` | `edgeenv.result.v1` | Required for newly written files. Missing marker is treated as legacy v1 only when the shape validates. Unknown marker is rejected. |
| Failed-run diagnostic | `.edgeenv/failed-runs/<run_id>/failure.json` | `edgeenv.failed-run.v1` | Required. Unknown marker is rejected. |
| Sampler metadata | `.edgeenv/runs/<run_id>/sampler/metadata.json` | `edgeenv.sampler-metadata.v1` | Optional artifact. If present, marker is required and unknown marker is rejected. |
| Export manifest | `<run_id>/manifest.json` inside zip | `edgeenv.export.v1` | Required. Unknown marker is rejected before extraction. |
| SQLite registry | `.edgeenv/runs.db` | Internal schema table/migration logic | Rebuildable local index. It is not canonical exported evidence. |

### Additive v1 Changes

Small additive changes can remain `v1` when all of these are true:

- Existing required fields keep the same meaning and type.
- New fields are optional or have safe defaults.
- Comparability rules do not change for existing runs.
- Export/import can preserve older bundles without requiring new files.
- Tests prove older v1 artifacts still load and compare the same way.

Examples:

- Adding an optional resource evidence field to `ResourceMetrics`.
- Adding an optional display-only sampler metadata key.
- Adding a read-only report that summarizes existing artifacts without mutating them.

### Migration-Required Changes

A new schema marker or migration design is required when any of these are true:

- A required field is renamed, removed, or changes type.
- `model_hash`, protocol fields, or comparability gates change meaning.
- The artifact layout requires a file that older bundles do not have.
- Sampler metadata raw artifact paths change interpretation.
- Export/import needs to transform artifact bytes rather than preserve them.
- Registry query columns become necessary for a field that was previously artifact-only.

Migration design must define:

- accepted source schema versions
- rejected future or incompatible versions
- exact field transforms
- whether compare output is unchanged, warning-only, or blocked
- registry rebuild behavior
- tests with old, current, corrupt, and future-version fixtures

## 4. HOW NOT — What To Avoid

- Do not silently import unknown future `result.json`, `failure.json`, `sampler/metadata.json`, or manifest schemas.
- Do not treat checksum validation as schema migration. Checksums prove bytes, not semantic compatibility.
- Do not export `runs.db` as canonical evidence or depend on registry rows to interpret bundles.
- Do not add resource metrics or sampler metadata to the comparability gate without a separate compare policy change.
- Do not turn schema migration into deployment validation, ranking, auth, dashboard, cloud sync, Docker, WSL, SSH, or model upload behavior.
- Do not rewrite existing v1 artifact semantics without compatibility tests.

## 5. WHERE — Related Design Boundaries

- [Export/Import Design](export-import-design.md) validates archive shape, checksums, manifest schema, required files, and safe paths before import.
- [Sampler Metadata Artifact Policy](sampler-metadata-artifact-policy.md) keeps sampler metadata optional and separate from `result.json`.
- [Evidence Contract Conformance Suite](evidence-contract-conformance-suite.md) proves valid/corrupt evidence behavior at the CLI contract level.
- [Registry Resource Query Design](registry-resource-query-design.md) keeps resource query indexes rebuildable from artifacts.
- [Compare Workflow Guide](compare-workflow-guide.md) keeps same-condition/conditional/no comparability judgement protocol-first.

## 6. WHY — Background Judgment

InferEdgeEnv is a local-first run evidence registry and comparability checker. Evidence bundles may outlive the code version that created them, so readers must know whether a file is current, legacy-compatible, or unsupported.

The safest policy is explicit compatibility:

- Current v1 files are accepted.
- Legacy files missing `result.json.schema_version` can be interpreted as v1 only when the full result shape validates.
- Unknown future schema markers are rejected until a migration exists.
- Registry rows stay rebuildable and never replace artifact validation.

This preserves the project boundary: InferEdgeEnv records whether benchmark evidence can be trusted and compared; it does not decide whether a model should deploy.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
