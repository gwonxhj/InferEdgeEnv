# Export/Import Design

## 1. WHAT — 이 문서가 정하는 것

성공 run evidence bundle인 `.edgeenv/runs/<run_id>/`를 zip으로 내보내고, 다른 workspace에서 검증 가능한 evidence로 다시 들여오기 위한 v1.1 설계 기준을 정한다.

이 문서는 구현이 아니라 contract design이다. 현재 MVP는 export/import command를 제공하지 않는다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `.edgeenv/runs/<run_id>/result.json` — canonical successful run result
- `.edgeenv/runs/<run_id>/config.yaml` — original benchmark config evidence
- `.edgeenv/runs/<run_id>/target.yaml` — original target profile evidence
- `.edgeenv/runs/<run_id>/env.json` — captured environment evidence
- `.edgeenv/runs/<run_id>/stdout.log` — captured benchmark stdout
- `.edgeenv/runs/<run_id>/stderr.log` — captured benchmark stderr
- `.edgeenv/runs.db` — local successful-run index, not canonical export evidence
- `inferedge_env/result/schema.py` — `edgeenv.result.v1` validation target
- `inferedge_env/registry/db.py` — future import registry insertion/rebuild path

기술 스택: zip archive, JSON manifest, SHA-256 checksums, existing Pydantic result schema, local filesystem

## 3. HOW — export/import contract

### Export scope

Export one successful run at a time:

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

### Import validation order

Future import should validate in this order:

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
12. Copy files into `.edgeenv/runs/<run_id>/` only if the destination does not already exist, unless a future explicit `--replace` policy is designed.
13. Insert or rebuild the local registry row from `result.json`, with `result_path` pointing at the imported artifact.

### Registry policy

`runs.db` should not be exported as canonical evidence. It is a local index.

Import should rebuild the registry row from `result.json` rather than trusting an exported SQLite row. This keeps portability independent of local paths, SQLite versions, and registry migration state.

If a run id already exists locally, default import should fail with a clear message. A future `--replace` or `--alias-run-id` policy needs a separate design because changing `run_id` affects compare references and artifact identity.

### Checksum policy

Use SHA-256 for every exported file. The checksum covers exact bytes in the archive, including log files.

The manifest itself is not self-checksummed in v1.1. If tamper-evidence beyond accidental corruption is needed later, use a detached signature design rather than overloading this manifest.

### Failed-run exports

Failed-run export is out of scope for the first export/import implementation. Failed-run artifacts use a different schema marker, are diagnostic rather than successful benchmark evidence, and should have a separate `bundle_type` such as `failed-run` if implemented later.

## 4. HOW NOT — 피해야 할 함정

- Do not export `runs.db` as the source of truth.
- Do not import directly into registry without validating and copying the artifact bundle.
- Do not accept zip entries with absolute paths, `..`, symlinks, or duplicate names.
- Do not silently overwrite an existing `.edgeenv/runs/<run_id>/`.
- Do not include model or dataset blobs by default. `model_path` and `model_hash` are identity evidence, not artifact upload semantics.
- Do not turn export/import into cloud sync, auth, public leaderboard, or model upload behavior.
- Do not export failed-run artifacts through the successful-run bundle contract.

## 5. WHERE — 다른 설계와의 관계

- **Result schema**: `result.json` remains the canonical successful-run data.
- **Registry**: `runs.db` remains a rebuildable local index.
- **Compare Workflow**: imported runs can be compared only after normal comparability judgement.
- **Failed Run Inspection**: failed-run artifacts stay diagnostic and out of this successful-run export scope.
- **Local Command Contract**: stdout/stderr/config/target/env files preserve evidence for later review.

## 6. WHY — 배경 판단

EdgeEnv의 evidence는 local registry row가 아니라 artifact bundle이다. Export/import should move that evidence without making claims about trust, ranking, or environment equivalence. The safest first design is therefore artifact-first: verify bytes, validate schema, copy evidence, then rebuild the local index.

This keeps the future implementation small and reversible while preserving the MVP boundary: local-first benchmark result recording and comparability judgement.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
