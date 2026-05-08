# Jetson Sampled Bundle Portability Review

## 1. WHAT — 이 문서가 정하는 것

Jetson sampled evidence bundle handoff 이후, raw `manifest.json`과 smoke output만으로 충분한지 검토하고 사람이 읽기 쉬운 handoff report가 필요한 경우의 최소 형식을 정한다.

결론: 짧은 human-readable handoff report는 필요하다. 다만 v1에서는 새 CLI command나 generated report artifact로 만들지 않고, PR/릴리스/외부 전달 문서에 붙일 수 있는 Markdown summary template으로 유지한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `docs/jetson-sampled-evidence-bundle-handoff.md` — 실제 `nano01` sampled bundle export/import 검증 기록
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — source/import/bundle root에서 raw validation을 수행하는 smoke
- `docs/export-import-design.md` — manifest/checksum/path-safety/source-of-truth contract
- `docs/sampler-metadata-artifact-policy.md` — sampler metadata/raw artifact portability policy
- `docs/compare-workflow-guide.md` — compare output interpretation rules
- `docs/bundle-report-generation-design.md` — future read-only generator contract for this Markdown summary
- `docs/v1-handoff-status.md` — next work snapshot

기술 스택: Markdown, EdgeEnv successful-run zip manifest, `report compare` output

## 3. HOW — report decision and template

### Why raw manifest is not enough

The manifest answers integrity questions:

- which files are in the bundle
- whether SHA-256 and byte size match
- whether the bundle type and run id are valid
- whether sampler metadata/raw artifacts are present

It does not answer reviewer questions quickly:

- what scenario this run pair belongs to
- whether the imported compare mode is expected
- whether metric deltas are allowed or suppressed
- whether sampler/resource evidence stayed supplemental
- whether `runs.db` was excluded and rebuilt

### Why smoke output is not enough

The smoke output is authoritative for validation, but it is intentionally verbose. It includes repeated `runs sampler show` JSON, archive paths, and full compare output. That is useful for debugging, but noisy for a PR reviewer, release note, or evidence handoff recipient.

### Decision

Use a short Markdown handoff report when sampled run bundles are shared outside the local workspace.

Do not add a new CLI command in v1. The CLI already exports/imports bundles and reports compare results. A generated report command should wait until the report fields stabilize across at least Jetson sampled evidence and one non-Jetson local evidence flow.

### Minimal handoff report template

```markdown
# EdgeEnv Sampled Evidence Bundle Handoff

## Scope

- Source device:
- EdgeEnv version:
- Bundle type: successful-run
- Export/import validation:
- Import registry policy: runs.db excluded, registry rebuilt from result.json

## Bundles

| Scenario | Run A | Run B | Exported files | Sampler evidence | Resource source |
| --- | --- | --- | --- | --- | --- |
| same-condition |  |  | core + sampler | metadata + raw log | jetson-tegrastats |
| runtime-conditional |  |  | core + sampler | metadata + raw log | jetson-tegrastats |
| target-conditional |  |  | core + sampler | metadata + raw log | jetson-tegrastats |

## Imported Compare Results

| Scenario | Comparable | Mode | Metrics Delta | Expected |
| --- | --- | --- | --- | --- |
| same-condition | Yes | same-condition | present | yes |
| runtime-conditional | Conditional | runtime-comparison | absent | yes |
| target-conditional | Conditional | target-comparison | absent | yes |

## Evidence Integrity

- Manifest schema:
- Required files present:
- Sampler metadata present:
- Raw sampler artifacts present:
- SHA-256/byte-size verification:
- Unsafe paths/runs.db excluded:

## Notes

- Sampler/resource evidence was supplemental and did not appear as a compare judgement reason.
- No model, dataset, engine, cloud DB, auth, dashboard, leaderboard, or target remote execution semantics are included.
```

### Filled example from `nano01`

```markdown
# EdgeEnv Sampled Evidence Bundle Handoff

## Scope

- Source device: nano01
- EdgeEnv version: 0.1.2
- Bundle type: successful-run
- Export/import validation: passed
- Import registry policy: runs.db excluded, registry rebuilt from result.json

## Bundles

| Scenario | Run A | Run B | Exported files | Sampler evidence | Resource source |
| --- | --- | --- | --- | --- | --- |
| same-condition | run-20260508-023720-b956f91e | run-20260508-023723-0b6c7a00 | core + sampler | metadata + raw log | jetson-tegrastats |
| runtime-conditional | run-20260508-023725-b2268b9b | run-20260508-023728-eab5b554 | core + sampler | metadata + raw log | jetson-tegrastats |
| target-conditional | run-20260508-023731-dad35067 | run-20260508-023734-e07834ec | core + sampler | metadata + raw log | jetson-tegrastats |

## Imported Compare Results

| Scenario | Comparable | Mode | Metrics Delta | Expected |
| --- | --- | --- | --- | --- |
| same-condition | Yes | same-condition | present | yes |
| runtime-conditional | Conditional | runtime-comparison | absent | yes |
| target-conditional | Conditional | target-comparison | absent | yes |

## Evidence Integrity

- Manifest schema: edgeenv.export.v1
- Required files present: result/config/target/env/stdout/stderr
- Sampler metadata present: sampler/metadata.json
- Raw sampler artifacts present: sampler/tegrastats.log
- SHA-256/byte-size verification: passed
- Unsafe paths/runs.db excluded: passed
```

## 4. HOW NOT — 피해야 할 함정

- Do not make the report a source of truth. `result.json`, `sampler/metadata.json`, raw artifacts, and manifest checksums remain canonical evidence.
- Do not include a composite score, ranking, leaderboard position, or model/environment standardization claim.
- Do not turn the report into model, dataset, or engine packaging.
- Do not hide conditional compare status behind metric deltas.
- Do not include local-only absolute artifact paths unless the report is explicitly for local debugging.
- Do not require this report for import; bundle validation must remain machine-verifiable without a human-written summary.

## 5. WHERE — 다른 설계와의 관계

- **Jetson Sampled Evidence Bundle Handoff**: provides the raw validation record that this report summarizes.
- **Export/Import Design**: remains the canonical bundle validation contract.
- **Compare Workflow Guide**: defines `Comparable`, `Mode`, and `Metrics Delta` interpretation.
- **Sampler Metadata Artifact Policy**: defines how sampler metadata/raw artifacts remain optional extension evidence.
- **V1 Handoff Status**: uses this review to decide the next development bundle.

## 6. WHY — 배경 판단

EdgeEnv evidence must be machine-verifiable, but project handoff also needs fast human scanning. A manifest is too low-level for reviewers, and full smoke logs are too noisy. A short Markdown report gives enough context to understand what was moved, what was verified, and how compare interpreted it, without creating a second source of truth.

Deferring CLI generation keeps the MVP clean. If future users repeatedly need the same report, a later `runs export --report` or `report bundle-summary` design can generate this template from imported artifacts and compare output.

That future generator contract is defined in [Bundle Report Generation Design](bundle-report-generation-design.md). It keeps the generated report outside zip bundles and reuses normal compare judgement.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Handoff reports should summarize imported compare outcomes, but must not replace manifest/checksum validation or result schema evidence.
