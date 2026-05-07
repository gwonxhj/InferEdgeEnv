# Export/Import Design

## 1. WHAT — 이 문서가 정하는 것

성공 run evidence bundle인 `.edgeenv/runs/<run_id>/`와 실패 run diagnostic evidence bundle인 `.edgeenv/failed-runs/<run_id>/`를 zip으로 내보내고, 다른 workspace에서 검증 가능한 evidence로 다시 들여오기 위한 v1.1 설계 기준을 정한다.

현재 구현은 successful run export/import와 failed-run export/import를 제공한다. Replace/alias import policy와 detached signatures는 future work다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `.edgeenv/runs/<run_id>/result.json` — canonical successful run result
- `.edgeenv/runs/<run_id>/config.yaml` — original benchmark config evidence
- `.edgeenv/runs/<run_id>/target.yaml` — original target profile evidence
- `.edgeenv/runs/<run_id>/env.json` — captured environment evidence
- `.edgeenv/runs/<run_id>/stdout.log` — captured benchmark stdout
- `.edgeenv/runs/<run_id>/stderr.log` — captured benchmark stderr
- `.edgeenv/runs/<run_id>/sampler/metadata.json` — optional future sampler metadata extension evidence
- `.edgeenv/failed-runs/<run_id>/failure.json` — canonical failed-run diagnostic metadata
- `.edgeenv/runs.db` — local successful-run index, not canonical export evidence
- `inferedge_env/result/schema.py` — `edgeenv.result.v1` validation target
- `inferedge_env/result/exporter.py` — successful/failed run zip export/import, manifest/checksum generation, safe import validation
- `inferedge_env/registry/db.py` — import registry insertion/rebuild path

기술 스택: zip archive, JSON manifest, SHA-256 checksums, existing Pydantic result schema, local filesystem

## 3. HOW — export/import contract

### Export scope

Export one successful run at a time:

```bash
edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip
```

```text
.edgeenv/runs/<run_id>/
  result.json
  config.yaml
  target.yaml
  env.json
  stdout.log
  stderr.log
```

The exported zip should contain a single top-level directory named with the run id:

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
```

`manifest.json` is added by export and is not part of the current run artifact layout.

### Manifest shape

Proposed `manifest.json`:

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

Every file in the archive except `manifest.json` must appear in `files`. Import must verify SHA-256 and byte size before trusting `result.json`.

### Required files

Required files for successful-run export/import:

- `result.json`
- `config.yaml`
- `target.yaml`
- `env.json`
- `stdout.log`
- `stderr.log`

Import must reject bundles that are missing any required file.

### Import command

Import a successful run evidence bundle:

```bash
edgeenv runs import edgeenv-run-<run_id>.zip
```

The command validates the zip bundle, copies required files into `.edgeenv/runs/<run_id>/`, and rebuilds the local registry row from `result.json`.

### Import validation order

Import validates in this order:

1. Open zip without extracting outside the destination root.
2. Require exactly one top-level run directory.
3. Read and validate `manifest.json`.
4. Reject unsupported `schema_version`.
5. Reject `bundle_type` values other than `successful-run` for this design.
6. Reject path traversal, absolute paths, symlinks, and duplicate archive entries.
7. Verify each required file exists.
8. Verify each file checksum and byte size.
9. Validate `result.json` against `RunResult`.
10. Require `manifest.run_id == result.run_id`.
11. Require archive directory name to match `run_id`.
12. Copy files into `.edgeenv/runs/<run_id>/` only if the destination does not already exist.
13. Insert or rebuild the local registry row from `result.json`, with `result_path` pointing at the imported artifact.

### Registry policy

`runs.db` should not be exported as canonical evidence. It is a local index.

Import should rebuild the registry row from `result.json` rather than trusting an exported SQLite row. This keeps portability independent of local paths, SQLite versions, and registry migration state.

If a run id already exists locally, import fails with a clear message. A future `--replace` or `--alias-run-id` policy needs a separate design because changing `run_id` affects compare references and artifact identity.

### Checksum policy

Use SHA-256 for every exported file. The checksum covers exact bytes in the archive, including log files.

The manifest itself is not self-checksummed in v1.1. If tamper-evidence beyond accidental corruption is needed later, use a detached signature design rather than overloading this manifest.

### Failed-run export/import

Failed-run artifacts use a different schema marker and stay diagnostic rather than successful benchmark evidence. Export/import uses `bundle_type: failed-run` and requires:

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

### Sampler artifact extension

Sampler metadata and raw sampler logs are optional extension evidence, not required successful-run files.

Future export/import support should include these only when present:

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
- Import must apply the same path traversal, symlink, duplicate entry, checksum, and byte-size validation to sampler files.
- Registry rebuild still uses `result.json`; sampler metadata must not become a registry source of truth.

Detailed storage policy is defined in [Sampler Metadata Artifact Policy](sampler-metadata-artifact-policy.md).

## 4. HOW NOT — 피해야 할 함정

- Do not export `runs.db` as the source of truth.
- Do not import directly into registry without validating and copying the artifact bundle.
- Do not accept zip entries with absolute paths, `..`, symlinks, or duplicate names.
- Do not silently overwrite an existing `.edgeenv/runs/<run_id>/`.
- Do not include model or dataset blobs by default. `model_path` and `model_hash` are identity evidence, not artifact upload semantics.
- Do not turn export/import into cloud sync, auth, public leaderboard, or model upload behavior.
- Do not export failed-run artifacts through the successful-run bundle contract.
- Do not import failed-run artifacts into `runs.db` or allow `report compare` to compare them.
- Do not make optional sampler artifacts required for successful-run import.

## 5. WHERE — 다른 설계와의 관계

- **Result schema**: `result.json` remains the canonical successful-run data.
- **Registry**: `runs.db` remains a rebuildable local index.
- **Compare Workflow**: imported runs can be compared only after normal comparability judgement.
- **Failed Run Inspection**: failed-run artifacts stay diagnostic and portable, but out of the successful-run registry/compare path.
- **Local Command Contract**: stdout/stderr/config/target/env files preserve evidence for later review.
- **Sampler Metadata Artifact Policy**: sampler metadata stays in optional `sampler/metadata.json` extension evidence.

## 6. WHY — 배경 판단

EdgeEnv의 evidence는 local registry row가 아니라 artifact bundle이다. Export/import should move that evidence without making claims about trust, ranking, or environment equivalence. The safest first design is therefore artifact-first: verify bytes, validate schema, copy evidence, then rebuild the local index.

This keeps the future implementation small and reversible while preserving the MVP boundary: local-first benchmark result recording and comparability judgement.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
