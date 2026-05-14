# Jetson Sampled Evidence Bundle Handoff

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Jetson sampled run evidence를 zip bundle로 export/import한 뒤에도 compare 판단이 그대로 유지되는지 확인한다.

검증 범위는 세 가지다.

- same-condition sampled runs: imported bundle compare가 `Comparable: Yes`, `Mode: same-condition`, `Metrics Delta`를 유지한다.
- runtime/provider conditional sampled runs: imported bundle compare가 `Comparable: Conditional`, `Mode: runtime-comparison`, no `Metrics Delta`를 유지한다.
- target conditional sampled runs: imported bundle compare가 `Comparable: Conditional`, `Mode: target-comparison`, no `Metrics Delta`를 유지한다.

이 handoff의 핵심은 `.edgeenv/runs/<run_id>/` artifact bundle이 portable evidence이고, `runs.db`는 import 후 rebuild되는 local index라는 점을 실측 Jetson sampled evidence로 확인하는 것이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — same/runtime/target sampled runs를 export/import 후 imported compare와 optional bundle-summary까지 검증하는 Jetson smoke
- `scripts/smoke_jetson_source_env.sh` — single sampled run export/import smoke
- `scripts/smoke_jetson_sampled_compare.sh` — same-condition sampled compare smoke
- `scripts/smoke_jetson_sampled_conditional_compare.sh` — runtime/provider conditional sampled compare smoke
- `scripts/smoke_jetson_sampled_target_compare.sh` — target conditional sampled compare smoke
- `docs/export-import-design.md` — manifest/checksum/path-safety/source-of-truth contract
- `docs/sampler-metadata-artifact-policy.md` — optional `sampler/metadata.json` and raw artifact portability rules
- `docs/compare-workflow-guide.md` — compare output interpretation rules
- `docs/jetson-sampled-bundle-portability-review.md` — human-readable summary format for sharing sampled evidence bundle outcomes
- `docs/jetson-bundle-summary-rehearsal.md` — generated Markdown summary validation against imported sampled bundle runs

기술 스택: Jetson Linux, `tegrastats`, EdgeEnv local runner, successful-run export/import zip, manifest SHA-256, SQLite registry rebuild, `report compare`

## 3. HOW — 리허설 절차

From the repo root on Jetson:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

What the script checks:

- runtime dependencies and `tegrastats` are available
- base sampled benchmark config validates
- temporary provider and target variants validate
- six sampled runs are created for same-condition, runtime-conditional, and target-conditional pairs
- every run has `resource_metrics.source=jetson-tegrastats`
- every run has `sampler/metadata.json` and listed raw sampler artifacts
- every run exports as a `successful-run` evidence zip
- every zip has a single top-level run directory and no `runs.db`
- every manifest includes the six required successful-run files
- every manifest includes optional sampler metadata and listed raw sampler artifacts
- every manifest file entry has a matching SHA-256 and byte size
- every bundle imports into a fresh registry root
- imported `result.json` matches the source `result.json`
- imported sampler metadata/raw artifacts are present
- imported same-condition compare still prints `Metrics Delta`
- imported runtime/target conditional compares suppress `Metrics Delta`
- imported compare output does not mention resource or sampler evidence as a judgement gate
- optional `--bundle-summary-output` writes a Markdown handoff summary from imported runs and validates same/conditional rows

By default the script uses temporary `/tmp/InferEdgeEnv-jetson-bundle-*`
directories and deletes only those temporary directories on success. If you pass
custom `--edgeenv-root`, `--import-root`, or `--bundle-dir` paths, they must not
already exist and will not be deleted automatically.

To include generated Markdown handoff smoke in the same run:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --keep-artifacts
```

Manual equivalent:

```bash
export PYTHONPATH="$PWD"
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$source_root"
edgeenv runs export <run_id> --output "$bundle_dir/edgeenv-run-<run_id>.zip" --edgeenv-root "$source_root"
edgeenv runs import "$bundle_dir/edgeenv-run-<run_id>.zip" --edgeenv-root "$import_root"
edgeenv report compare <imported_run_id_a> <imported_run_id_b> --edgeenv-root "$import_root"
```

Repeat that flow for:

- two identical sampled configs/profiles
- one provider-variant benchmark config
- one target-variant profile

## 4. HOW NOT — 피해야 할 함정

- Do not export `runs.db`; import must rebuild it from `result.json`.
- Do not treat `sampler/metadata.json` as required for old bundles, but do require it when validating this sampled rehearsal.
- Do not accept a bundle as portable if listed raw sampler artifacts are missing from the zip or manifest.
- Do not let resource metrics or sampler metadata change compare mode after import.
- Do not print latency/throughput `Metrics Delta` for runtime or target conditional imported compares.
- Do not use this as model, dataset, engine, or public leaderboard packaging.
- Do not describe this as SSH/remote target support; execution still happens locally on Jetson.
- Do not commit generated `.edgeenv/`, zip bundles, raw `tegrastats` logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Export/Import Design**: this validates successful-run bundle manifest, checksum, optional sampler extension, and registry rebuild policy.
- **Sampler Metadata Artifact Policy**: this confirms `sampler/metadata.json` and raw artifacts move with the run bundle.
- **Compare Workflow Guide**: this confirms imported evidence still goes through normal comparability judgement.
- **Jetson Sampled Comparison Rehearsal**: this extends same-condition sampled compare through export/import.
- **Jetson Sampled Conditional Comparison Rehearsal**: this extends runtime/provider conditional sampled compare through export/import.
- **Jetson Sampled Target Comparison Rehearsal**: this extends target conditional sampled compare through export/import.
- **Jetson Sampled Bundle Portability Review**: this decides how to summarize the raw manifest and smoke output for humans without creating a new source of truth.
- **Jetson Bundle Summary Rehearsal**: this confirms that the handoff summary can be generated from imported sampled bundle runs.

## 6. WHY — 배경 판단

Export/import is where the local-first evidence model either holds or leaks. A run bundle should be enough to move successful benchmark evidence to another workspace, but it must not smuggle in local registry state or imply that sampled resource metrics are compare gates.

This rehearsal deliberately checks portability and interpretation together: the bytes move through manifest/checksum validation, then compare still starts from benchmark protocol and identity rather than sampler/resource evidence.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Sampled evidence bundle handoff should validate both archive portability and imported compare output; checking only zip contents misses compare contract drift.

## Validation Record — nano01

Status: passed on `nano01`.

Command:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

Observed run pairs:

```text
same-condition:
run-20260508-023720-b956f91e
run-20260508-023723-0b6c7a00

runtime-conditional:
run-20260508-023725-b2268b9b
run-20260508-023728-eab5b554

target-conditional:
run-20260508-023731-dad35067
run-20260508-023734-e07834ec
```

Observed bundle manifest shape for every run:

```text
bundle_type: successful-run
manifest files:
- config.yaml
- env.json
- result.json
- sampler/metadata.json
- sampler/tegrastats.log
- stderr.log
- stdout.log
- target.yaml
resource_metrics.source: jetson-tegrastats
sample_count: 3
raw_artifacts: sampler/tegrastats.log
```

Observed imported same-condition compare:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
- latency_mean_ms: 12.3 ms -> 12.3 ms (delta 0.0 ms, +0.00%)
```

Observed imported runtime-conditional compare:

```text
Comparable: Conditional
Mode: runtime-comparison
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
- Different runtime or execution provider
```

Observed imported target-conditional compare:

```text
Comparable: Conditional
Mode: target-comparison
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
- Different target
```

Conclusion:

- All six sampled run bundles exported and imported successfully.
- `runs.db` was not part of the exported evidence; import rebuilt registry rows from `result.json`.
- Every imported run preserved `sampler/metadata.json` and `sampler/tegrastats.log`.
- Manifest SHA-256 and byte-size entries matched archive bytes for all listed files.
- Imported same-condition compare retained supplemental `Metrics Delta`.
- Imported runtime/target conditional compares suppressed `Metrics Delta`.
- Resource and sampler evidence did not appear as compare judgement reasons.

Follow-up:

- [Jetson Bundle Summary Rehearsal](jetson-bundle-summary-rehearsal.md) generated the Markdown handoff summary from imported sampled bundle runs and confirmed same-condition delta presence plus conditional delta suppression.
- `scripts/smoke_jetson_sampled_bundle_handoff.sh --bundle-summary-output <path>` now automates that generated Markdown check for repeated release rehearsal.
