# Bundle Report Generation Design

## 1. WHAT — 이 문서가 정하는 것

sampled evidence bundle handoff report를 사람이 직접 작성하지 않고 자동 생성할 때 어떤 입력과 출력 계약을 가져야 하는지 정한다.

결정: `report bundle-summary` 형태의 read-only Markdown generator로 시작한다. 이 generator는 imported run artifacts와 `report compare` 판단을 요약할 뿐, bundle validation이나 compare 판단을 대체하지 않는다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `docs/jetson-sampled-bundle-portability-review.md` — 수동 Markdown handoff report template
- `docs/jetson-sampled-evidence-bundle-handoff.md` — real Jetson sampled bundle export/import validation record
- `docs/jetson-bundle-summary-rehearsal.md` — real imported Jetson sampled bundle summary generation record
- `docs/export-import-design.md` — successful-run bundle manifest/checksum/import contract
- `docs/compare-workflow-guide.md` — `Comparable`, `Mode`, `Metrics Delta` interpretation
- `inferedge_env/cli.py` — `report bundle-summary` command surface
- `inferedge_env/report/bundle_summary.py` — read-only Markdown generator implementation
- `inferedge_env/compare/comparability.py` — compare judgement source
- `inferedge_env/result/exporter.py` — manifest validation source, not report source of truth

기술 스택: Typer/Rich CLI, Markdown text output, existing registry/result artifact readers, comparability checker

## 3. HOW — proposed generator contract

### Command shape

CLI shape:

```bash
edgeenv report bundle-summary \
  --scenario same-condition:<run_id_a>:<run_id_b> \
  --scenario runtime-conditional:<run_id_a>:<run_id_b> \
  --scenario target-conditional:<run_id_a>:<run_id_b> \
  --edgeenv-root .edgeenv \
  --output edgeenv-bundle-handoff.md
```

Why this shape:

- It keeps report generation under `report`, not under `runs export`, because the report summarizes compare outcomes across multiple imported run pairs.
- It does not mutate run artifacts or zip bundles.
- It lets the caller name scenarios explicitly instead of inferring intent from runtime/target differences.
- It can run against an imported registry root after `edgeenv runs import`.

### Inputs

Required inputs:

- existing successful run ids in a registry root
- scenario labels supplied by the caller
- run artifacts reachable through registry `result_path`
- normal comparability judgement from the existing compare checker

Optional inputs:

- source device name
- EdgeEnv version override, otherwise use package version
- free-form notes for a PR/release handoff
- output path, otherwise print Markdown to stdout

The generator should read:

- `result.json`
- `sampler/metadata.json` when present
- raw artifact paths listed by sampler metadata
- compare judgement and optional metric delta from the same code path as `edgeenv report compare`

The generator should not read:

- `runs.db` as evidence beyond resolving run ids to artifact paths
- local zip archives after import
- model, dataset, or engine blobs
- raw sampler log contents unless a future explicit diagnostics mode needs it

### Output

The output is Markdown matching the manual handoff report template:

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

## Imported Compare Results

| Scenario | Comparable | Mode | Metrics Delta | Expected |
| --- | --- | --- | --- | --- |

## Evidence Integrity

- Manifest schema:
- Required files present:
- Sampler metadata present:
- Raw sampler artifacts present:
- SHA-256/byte-size verification:
- Unsafe paths/runs.db excluded:

## Notes

- Sampler/resource evidence was supplemental and did not appear as a compare judgement reason.
```

The generated report should be deterministic except for caller-provided notes and the order of scenarios, which should follow the command-line order.

### Evidence integrity fields

For imported run directories, the generator can confirm artifact presence:

- required successful-run files exist
- `sampler/metadata.json` exists when sampler evidence is expected
- listed raw sampler artifacts exist
- `result.json.resource_metrics.source` is present when resource metrics were recorded

It cannot prove original zip checksum validation after the zip is no longer present. Therefore the report should say:

```text
SHA-256/byte-size verification: previously validated during import
```

If a future `--bundle-dir` option is added, it may validate manifests directly and say:

```text
SHA-256/byte-size verification: passed
```

That should be a separate option, not required for the first generator.

### Compare summary rules

The generator must use the same rules as `report compare`:

- `Comparable: Yes` + `Mode: same-condition` may show metric delta status as `present`.
- `Comparable: Conditional` must show metric delta status as `absent`.
- `Comparable: No` must show metric delta status as `absent`.
- Resource metrics and sampler metadata must never change `Comparable` or `Mode`.

The report may include only status-level metric delta information in the table. Full latency/throughput deltas should remain in `edgeenv report compare` output unless a later design adds an explicit detailed section.

### Failure behavior

Fail clearly when:

- a run id is missing from the registry
- `result.json` cannot be loaded
- a scenario argument is malformed
- a scenario label is duplicated
- a required run artifact is missing
- compare judgement cannot be produced

Warn, but keep generating, when:

- sampler metadata is absent
- raw sampler artifact references are absent because no sampler was used
- resource metrics are absent

Do not import bundles, export bundles, or write into `.edgeenv/runs/`.

### Tests

Minimum tests:

- generates Markdown for three scenario pairs from imported/fake run artifacts
- preserves command-line scenario order
- same-condition reports metric delta `present`
- runtime/target conditional reports metric delta `absent`
- missing sampler metadata does not fail
- missing required run artifact fails clearly
- output file write works and stdout mode works
- report text does not include ranking/composite score language

## 4. HOW NOT — 피해야 할 함정

- Do not make the generated report canonical evidence.
- Do not write the report into exported zip bundles by default.
- Do not reimplement compare rules in a separate report-only code path.
- Do not infer scenario labels from metrics or resource evidence.
- Do not include composite score, ranking, leaderboard, model upload, dataset upload, auth, cloud sync, Docker, WSL, or SSH target semantics.
- Do not show full metric deltas for conditional or non-comparable pairs.
- Do not treat missing optional sampler metadata as import failure.
- Do not require original zip bundles just to summarize already imported runs.

## 5. WHERE — 다른 설계와의 관계

- **Jetson Sampled Bundle Portability Review**: manual template is the source for the generated Markdown shape.
- **Export/Import Design**: bundle validation remains machine-verifiable and separate from report generation.
- **Compare Workflow Guide**: compare interpretation and metric delta suppression rules are reused.
- **Sampler Metadata Artifact Policy**: sampler evidence remains optional artifact evidence.
- **V1 Handoff Status**: this implementation closes the first generated report step and leaves richer bundle-dir validation as future work.
- **Jetson Bundle Summary Rehearsal**: confirms the generator output on real imported sampled Jetson evidence.

## 6. WHY — 배경 판단

Generated reports are useful only if they reduce repetitive human work without weakening the evidence model. The safe design is therefore a read-only summarizer over imported evidence and existing compare judgement.

Keeping the report outside zip bundles avoids a second truth source. Keeping scenario labels explicit avoids silent inference mistakes. Reusing `report compare` logic keeps EdgeEnv centered on comparability rather than score presentation.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Bundle report generation should summarize imported artifacts and compare output, not validate trust or create new benchmark claims.
