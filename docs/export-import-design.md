# Export/Import Design

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This document defines the v1.1 design contract for exporting a successful run evidence bundle from `.edgeenv/runs/<run_id>/`, exporting a failed-run diagnostic bundle from `.edgeenv/failed-runs/<run_id>/`, and importing those bundles into another workspace as verifiable evidence.

The current implementation supports successful-run export/import, optional runtime telemetry sidecar export/import, optional sampler artifact export/import, and failed-run export/import. Replace/alias import policy and detached signatures remain future work.

## 2. CONTENTS — Files And Stack

Related files:

- `.edgeenv/runs/<run_id>/result.json` — canonical successful run result
- `.edgeenv/runs/<run_id>/config.yaml` — original benchmark config evidence
- `.edgeenv/runs/<run_id>/target.yaml` — original target profile evidence
- `.edgeenv/runs/<run_id>/env.json` — captured environment evidence
- `.edgeenv/runs/<run_id>/stdout.log` — captured benchmark stdout
- `.edgeenv/runs/<run_id>/stderr.log` — captured benchmark stderr
- `.edgeenv/runs/<run_id>/runtime_telemetry.json` — optional runtime telemetry sidecar evidence
- `.edgeenv/runs/<run_id>/sampler/metadata.json` — optional sampler metadata extension evidence
- `.edgeenv/failed-runs/<run_id>/failure.json` — canonical failed-run diagnostic metadata
- `.edgeenv/runs.db` — local successful-run index, not canonical export evidence
- `inferedge_env/result/schema.py` — `edgeenv.result.v1` validation target
- `inferedge_env/result/exporter.py` — successful/failed run zip export/import, manifest/checksum generation, safe import validation
- `inferedge_env/registry/db.py` — import registry insertion/rebuild path
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — sampled Jetson same/runtime/target evidence bundle portability smoke
- `docs/jetson-sampled-bundle-portability-review.md` — optional human-readable handoff report format
- `docs/bundle-report-generation-design.md` — read-only report generation contract
- `docs/schema-versioning-migration-policy.md` — schema marker compatibility and unknown future-version rejection policy

Stack: zip archive, JSON manifest, SHA-256 checksums, Pydantic result schema, local filesystem artifacts

## 3. HOW — Export/Import Contract

### Export Scope

Export one successful run at a time:

```bash
edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip
```

Source artifact layout:

```text
.edgeenv/runs/<run_id>/
  result.json
  config.yaml
  target.yaml
  env.json
  stdout.log
  stderr.log
  runtime_telemetry.json  # optional
```

The exported zip contains a single top-level directory named with the run id:

```text
edgeenv-run-<run_id>.zip
  <run_id>/
    manifest.json
    result.json
    config.yaml
    target.yaml
    env.json
    stdout.log
    stderr.log
    runtime_telemetry.json  # optional
```

`manifest.json` is generated during export and is not part of the normal run artifact layout.

### Manifest Shape

`manifest.json` uses this shape:

```json
{
  "schema_version": "edgeenv.export.v1",
  "bundle_type": "successful-run",
  "run_id": "run-20260507-000000-12345678",
  "created_at": "2026-05-07T00:00:00+00:00",
  "source_result_schema_version": "edgeenv.result.v1",
  "files": [
    {
      "path": "result.json",
      "required": true,
      "sha256": "<hex>",
      "bytes": 1234
    }
  ],
  "exported_at": "2026-05-07T00:01:00+00:00",
  "exported_by": {
    "tool": "edgeenv",
    "package": "inferedge_env",
    "version": "0.1.0"
  }
}
```

Every archived file except `manifest.json` must appear in `files`. Import verifies SHA-256 and byte size before trusting `result.json`.

### Required Files

Successful-run export/import requires:

- `result.json`
- `config.yaml`
- `target.yaml`
- `env.json`
- `stdout.log`
- `stderr.log`

Import rejects bundles that are missing any required file.

### Import Command

Import a successful run evidence bundle:

```bash
edgeenv runs import edgeenv-run-<run_id>.zip
```

The command validates the zip bundle, copies required files into `.edgeenv/runs/<run_id>/`, and rebuilds the local registry row from `result.json`.

### Import Validation Order

Import validates in this order:

1. Open the zip without extracting outside the destination root.
2. Require exactly one top-level run directory.
3. Read and validate `manifest.json`.
4. Reject unsupported `schema_version`.
5. Reject `bundle_type` values other than `successful-run` for successful-run import.
6. Reject path traversal, absolute paths, symlinks, and duplicate archive entries.
7. Verify each required file exists.
8. Verify each file checksum and byte size.
9. Validate optional extension evidence such as `runtime_telemetry.json` and sampler files when present.
10. Validate `result.json` against `RunResult`.
11. Require `manifest.run_id == result.run_id`.
12. Require the archive directory name to match `run_id`.
13. Copy files into `.edgeenv/runs/<run_id>/` only if the destination does not already exist.
14. Insert or rebuild the local registry row from `result.json`, with `result_path` pointing at the imported artifact.

### Registry Policy

`runs.db` is a local index and should not be exported as canonical evidence.

Import rebuilds the registry row from `result.json` rather than trusting an exported SQLite row. This keeps portability independent of local paths, SQLite versions, and registry migration state.

If a run id already exists locally, import fails with a clear message. A future `--replace` or `--alias-run-id` policy needs a separate design because changing `run_id` affects compare references and artifact identity.

### Checksum Policy

Use SHA-256 for every exported file. The checksum covers exact bytes in the archive, including log files.

The manifest itself is not self-checksummed in v1.1. If tamper-evidence beyond accidental corruption is needed later, use a detached signature design rather than overloading this manifest.

### Failed-Run Export/Import

Failed-run artifacts use a different schema marker and remain diagnostic rather than successful benchmark evidence. Export/import uses `bundle_type: failed-run` and requires:

- `failure.json`
- `config.yaml`
- `target.yaml`
- `env.json`
- `stdout.log`
- `stderr.log`

Commands:

```bash
edgeenv failed-runs export <run_id> --output edgeenv-failed-run-<run_id>.zip
edgeenv failed-runs import edgeenv-failed-run-<run_id>.zip
```

Import validates the manifest, checksums, byte sizes, top-level run id, and `failure.json` schema marker before copying files into `.edgeenv/failed-runs/<run_id>/`. It does not insert or rebuild any `runs.db` row.

### Sampler Artifact Extension

Sampler metadata and raw sampler logs are optional extension evidence, not required successful-run files.

Export/import includes these only when present:

```text
<run_id>/
  sampler/
    metadata.json
    tegrastats.log
```

Rules:

- `sampler/metadata.json` is optional and must never be required for older bundles.
- If `sampler/metadata.json` exists, it must be listed in `manifest.files` with checksum and byte size.
- Every path listed in `sampler/metadata.json.raw_artifacts` must be present in the archive and manifest.
- Import applies the same path traversal, symlink, duplicate entry, checksum, and byte-size validation to sampler files.
- Registry rebuild still uses `result.json`; sampler metadata must not become a registry source of truth.

Detailed storage policy is defined in [Sampler Metadata Artifact Policy](sampler-metadata-artifact-policy.md).

### Runtime Telemetry Extension

Runtime telemetry is optional extension evidence, not a required successful-run file.

Export/import includes this sidecar only when present:

```text
<run_id>/
  runtime_telemetry.json
```

Rules:

- `runtime_telemetry.json` is optional and must never be required for older bundles.
- If present, it must be a JSON object and may include a string `schema_version`.
- It must be listed in `manifest.files` with checksum and byte size.
- Import applies the same path traversal, duplicate entry, checksum, and byte-size validation used for required files.
- Registry rebuild still uses `result.json`; runtime telemetry must not become a registry source of truth or a live monitoring store.

For real sampled Jetson evidence, [Jetson Sampled Evidence Bundle Handoff](jetson-sampled-evidence-bundle-handoff.md) exports and imports same-condition, runtime-conditional, and target-conditional run bundles, then compares the imported runs to confirm that bundle portability does not change comparability judgement.

[Jetson Sampled Bundle Portability Review](jetson-sampled-bundle-portability-review.md) defines a short Markdown report for people reviewing those bundles. The report summarizes manifest and compare outcomes, but it is not required for import and is not canonical evidence.

[Bundle Report Generation Design](bundle-report-generation-design.md) describes how that Markdown summary is generated from imported artifacts and compare output without mutating bundles.

[Schema Versioning And Migration Policy](schema-versioning-migration-policy.md) defines which artifact schema markers are accepted. Import rejects unknown future manifest, result, failed-run, or sampler metadata schema markers until a migration policy exists.

## 4. HOW NOT — What To Avoid

- Do not export `runs.db` as the source of truth.
- Do not import directly into the registry without validating and copying the artifact bundle.
- Do not accept zip entries with absolute paths, `..`, symlinks, or duplicate names.
- Do not silently overwrite an existing `.edgeenv/runs/<run_id>/`.
- Do not include model or dataset blobs by default. `model_path` and `model_hash` are identity evidence, not artifact upload semantics.
- Do not turn export/import into cloud sync, auth, public leaderboard, or model upload behavior.
- Do not export failed-run artifacts through the successful-run bundle contract.
- Do not import failed-run artifacts into `runs.db` or allow `report compare` to compare them.
- Do not make optional sampler artifacts required for successful-run import.
- Do not make optional runtime telemetry required for successful-run import or use it as a comparability gate.

## 5. WHERE — Related Design Boundaries

- **Result Schema**: `result.json` remains the canonical successful-run data.
- **Registry**: `runs.db` remains a rebuildable local index.
- **Compare Workflow**: imported runs can be compared only after normal comparability judgement.
- **Jetson Sampled Evidence Bundle Handoff**: validates imported sampled bundles against same-condition, runtime-conditional, and target-conditional compare paths.
- **Jetson Sampled Bundle Portability Review**: summarizes portable evidence for human handoff without replacing manifest validation.
- **Bundle Report Generation Design**: generated reports remain read-only summaries outside the evidence bundle.
- **Failed Run Inspection**: failed-run artifacts stay diagnostic and portable, but out of the successful-run registry/compare path.
- **Local Command Contract**: stdout/stderr/config/target/env files preserve evidence for later review.
- **Sampler Metadata Artifact Policy**: sampler metadata stays in optional `sampler/metadata.json` extension evidence.
- **Schema Versioning And Migration Policy**: schema markers gate semantic compatibility after checksum and path validation.

## 6. WHY — Background Judgment

EdgeEnv evidence is the artifact bundle, not the local registry row. Export/import should move that evidence without making claims about trust, ranking, or environment equivalence. The safest design is artifact-first: verify bytes, validate schema, copy evidence, then rebuild the local index.

This keeps the implementation small and reversible while preserving the project boundary: local-first run evidence registry and comparability judgement.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
