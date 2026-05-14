# Jetson Bundle Summary Rehearsal

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

실제 imported Jetson sampled evidence bundle runs를 대상으로 `edgeenv report bundle-summary`를 실행하고, 생성된 Markdown handoff summary가 기대한 compare 철학을 유지하는지 기록한다.

검증 범위는 세 가지 imported run pair다.

- same-condition: `Comparable: Yes`, `Mode: same-condition`, metric delta summary `present`
- runtime-conditional: `Comparable: Conditional`, `Mode: runtime-comparison`, metric delta summary `absent`
- target-conditional: `Comparable: Conditional`, `Mode: target-comparison`, metric delta summary `absent`

이 리허설은 report 생성이 실측 evidence handoff를 편하게 만들 수는 있지만, `result.json`, `sampler/metadata.json`, raw sampler artifacts, export manifest/checksum을 대체하지 않는다는 점을 확인한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/report/bundle_summary.py` — imported artifacts와 compare judgement를 읽어 Markdown을 생성하는 read-only generator
- `inferedge_env/cli.py` — `report bundle-summary` command surface
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — imported Jetson sampled bundle runs를 준비하고 compare와 optional bundle-summary까지 검증하는 smoke
- `docs/bundle-report-generation-design.md` — generator input/output/failure contract
- `docs/jetson-sampled-evidence-bundle-handoff.md` — successful-run bundle export/import validation record
- `docs/jetson-sampled-bundle-portability-review.md` — human-readable handoff report template

기술 스택: Jetson Linux, `tegrastats`, EdgeEnv successful-run export/import, SQLite registry rebuild, `report compare`, Markdown handoff summary

## 3. HOW — 리허설 절차

먼저 Jetson에서 sampled bundle handoff smoke를 실행해 source/imported bundle roots를 만든다.

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --edgeenv-root /tmp/InferEdgeEnv-jetson-summary.jdrYbb/source/.edgeenv \
  --import-root /tmp/InferEdgeEnv-jetson-summary.jdrYbb/imported/.edgeenv \
  --bundle-dir /tmp/InferEdgeEnv-jetson-summary.jdrYbb/bundles \
  --keep-artifacts
```

그 다음 imported registry root만 대상으로 summary를 생성한다.

```bash
python -m inferedge_env.cli report bundle-summary \
  --scenario same-condition:run-20260508-040809-0c61523a:run-20260508-040811-42caf723 \
  --scenario runtime-conditional:run-20260508-040814-28de6c30:run-20260508-040817-001d2fe1 \
  --scenario target-conditional:run-20260508-040819-3aa37b09:run-20260508-040822-13cca899 \
  --source-device nano01 \
  --edgeenv-root /tmp/InferEdgeEnv-jetson-summary.jdrYbb/imported/.edgeenv \
  --output /tmp/InferEdgeEnv-jetson-summary.jdrYbb/bundle-summary.md
```

Repeated release rehearsal can now do both steps in one smoke run:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-summary.md \
  --keep-artifacts
```

The optional summary smoke validates that the generated Markdown contains the same-condition scenario row, conditional compare rows with `Metrics Delta` absent, and no ranking table or composite score fields.

Expected behavior:

- command succeeds without modifying imported run artifacts
- generated Markdown lists all three scenarios in command-line order
- sampler evidence is reported as present for all sampled runs
- same-condition row shows `Metrics Delta` as `present`
- runtime/target conditional rows show `Metrics Delta` as `absent`
- report notes state that sampler/resource evidence is supplemental

## 4. HOW NOT — 피해야 할 함정

- Do not run the summary against the source root when the handoff claim is about imported evidence.
- Do not treat the generated Markdown as canonical evidence.
- Do not write generated summaries into `.edgeenv/runs/<run_id>/` or exported zip bundles by default.
- Do not add sampler/resource evidence to compare judgement reasons.
- Do not show latency/throughput delta summary for conditional or non-comparable pairs.
- Do not describe this as SSH target support; the Jetson command was a validation convenience, not an EdgeEnv remote runner.
- Do not commit generated `.edgeenv/`, zip bundles, raw `tegrastats` logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Bundle Report Generation Design**: this rehearsal validates the implemented read-only generator on real imported Jetson sampled runs.
- **Jetson Sampled Evidence Bundle Handoff**: this reuses the imported runs from the successful-run export/import handoff.
- **Jetson Sampled Bundle Portability Review**: this confirms the manual handoff template can be generated automatically.
- **Compare Workflow Guide**: this confirms the generated summary preserves same-condition delta and conditional delta suppression.
- **Export/Import Design**: this keeps manifest/checksum validation separate from report generation.

## 6. WHY — 배경 판단

사람이 evidence bundle을 넘겨받을 때는 zip manifest와 raw smoke output만으로 전체 흐름을 빠르게 이해하기 어렵다. `report bundle-summary`는 imported registry와 compare judgement를 읽어 짧은 Markdown을 만들지만, 신뢰의 원천은 여전히 imported run artifacts와 import-time manifest/checksum validation이다.

이 리허설은 기능 구현이 fake artifact 테스트만 통과한 상태를 넘어, 실제 Jetson sampled evidence handoff에서도 같은 요약이 생성되는지 닫는 단계다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Jetson bundle-summary rehearsal should use the imported `.edgeenv` root, because the report is meant to summarize handoff evidence after export/import.

## Validation Record — nano01

Status: passed on `nano01`.

Imported registry root:

```text
/tmp/InferEdgeEnv-jetson-summary.jdrYbb/imported/.edgeenv
```

Generated report:

```text
/tmp/InferEdgeEnv-jetson-summary.jdrYbb/bundle-summary.md
```

Observed run pairs:

```text
same-condition:
run-20260508-040809-0c61523a
run-20260508-040811-42caf723

runtime-conditional:
run-20260508-040814-28de6c30
run-20260508-040817-001d2fe1

target-conditional:
run-20260508-040819-3aa37b09
run-20260508-040822-13cca899
```

Command:

```bash
python -m inferedge_env.cli report bundle-summary \
  --scenario same-condition:run-20260508-040809-0c61523a:run-20260508-040811-42caf723 \
  --scenario runtime-conditional:run-20260508-040814-28de6c30:run-20260508-040817-001d2fe1 \
  --scenario target-conditional:run-20260508-040819-3aa37b09:run-20260508-040822-13cca899 \
  --source-device nano01 \
  --edgeenv-root /tmp/InferEdgeEnv-jetson-summary.jdrYbb/imported/.edgeenv \
  --output /tmp/InferEdgeEnv-jetson-summary.jdrYbb/bundle-summary.md
```

Observed output:

```text
Bundle summary written
Report: /tmp/InferEdgeEnv-jetson-summary.jdrYbb/bundle-summary.md
```

Generated Markdown:

```markdown
# EdgeEnv Sampled Evidence Bundle Handoff

## Scope

- Source device: nano01
- EdgeEnv version: 0.1.2
- Bundle type: successful-run
- Export/import validation: previously completed before summary generation
- Import registry policy: runs.db excluded, registry rebuilt from result.json

## Bundles

| Scenario | Run A | Run B | Exported files | Sampler evidence | Resource source |
| --- | --- | --- | --- | --- | --- |
| same-condition | run-20260508-040809-0c61523a | run-20260508-040811-42caf723 | core + sampler | metadata + raw log | jetson-tegrastats |
| runtime-conditional | run-20260508-040814-28de6c30 | run-20260508-040817-001d2fe1 | core + sampler | metadata + raw log | jetson-tegrastats |
| target-conditional | run-20260508-040819-3aa37b09 | run-20260508-040822-13cca899 | core + sampler | metadata + raw log | jetson-tegrastats |

## Imported Compare Results

| Scenario | Comparable | Mode | Metrics Delta | Expected |
| --- | --- | --- | --- | --- |
| same-condition | Yes | same-condition | present | yes |
| runtime-conditional | Conditional | runtime-comparison | absent | yes |
| target-conditional | Conditional | target-comparison | absent | yes |

## Evidence Integrity

- Manifest schema: edgeenv.export.v1
- Required files present: result/config/target/env/stdout/stderr
- Sampler metadata present: yes
- Raw sampler artifacts present: yes
- SHA-256/byte-size verification: previously validated during import
- Unsafe paths/runs.db excluded: previously validated during import

## Notes

- Sampler/resource evidence was supplemental and did not appear as a compare judgement reason.
- No model, dataset, engine, cloud DB, auth, dashboard, leaderboard, or target remote execution semantics are included.
```

Conclusion:

- `report bundle-summary` generated the expected Markdown from imported Jetson sampled run artifacts.
- Same-condition compare was summarized with metric delta present.
- Runtime/target conditional compares were summarized with metric delta absent.
- Sampler metadata and raw `tegrastats` evidence were visible as supplemental evidence only.
- The report did not mutate imported run artifacts or become part of the evidence bundle.

## Automation Note

`scripts/smoke_jetson_sampled_bundle_handoff.sh --bundle-summary-output <path>` automates this generated report check for repeated release rehearsal. The option remains opt-in because bundle-summary generation is a handoff convenience, not canonical evidence.

## Automation Validation — nano01

Status: passed on `nano01`.

Command shape:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output <workdir>/bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

Generated report:

```text
/tmp/InferEdgeEnv-bundle-summary-smoke.f7ZwFk/bundle-summary.md
```

Observed run pairs:

```text
same-condition:
run-20260508-054737-a14efcc2
run-20260508-054740-12125d60

runtime-conditional:
run-20260508-054743-4e82bef2
run-20260508-054745-0440b6fe

target-conditional:
run-20260508-054748-e529f75a
run-20260508-054751-4c0ffafb
```

Observed generated compare summary:

```text
| same-condition | Yes | same-condition | present | yes |
| runtime-conditional | Conditional | runtime-comparison | absent | yes |
| target-conditional | Conditional | target-comparison | absent | yes |
```

Conclusion:

- The Jetson sampled bundle handoff smoke generated and validated `bundle-summary.md` from the imported registry root.
- Same-condition delta status remained `present`.
- Runtime/target conditional delta status remained `absent`.
- The smoke rejected ranking table or composite score fields while allowing non-goal notes that mention unsupported leaderboard semantics.
