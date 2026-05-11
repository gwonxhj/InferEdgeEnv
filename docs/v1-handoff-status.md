# EdgeEnv MVP v1 Handoff Status

## 1. WHAT — 이 문서가 정하는 것

EdgeEnv MVP v1 기반의 현재 상태, 검증 방법, 남은 future work, 다음 개발자가 어디서 시작해야 하는지를 한 장으로 정리한다.

이 문서는 새 기능 설계가 아니라 handoff snapshot이다. 구현된 것과 아직 구현하지 않은 것을 섞지 않는 것이 목적이다.

## 2. CONTENTS — 현재 repo 상태

주요 구현 영역:

- Python package: `inferedge_env`
- User-facing CLI command: `edgeenv`
- Config schema: `inferedge_env/config/`
- Runner: `FakeRunner`, `LocalRunner`
- Result artifact writer: `inferedge_env/result/`
- SQLite registry: `inferedge_env/registry/`
- Comparability checker: `inferedge_env/compare/`
- Examples: `examples/`
- Tests: `tests/`
- Readiness CI: `.github/workflows/readiness.yml`

현재 기준 commit은 repo에서 `git log -1 --oneline`으로 확인한다. 이 문서는 특정 SHA보다 현재 MVP capability snapshot을 우선한다.

## 3. HOW — 현재 가능한 사용자 흐름

### Install and entrypoints

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

관련 문서:

- [Packaging And Entrypoint Readiness](packaging-entrypoints.md)
- [CI Readiness Workflow](ci-readiness.md)
- [EdgeEnv MVP v1 Release Rehearsal](v1-release-rehearsal.md)

### Fake run

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
```

Use this path when checking config/result/registry lifecycle without executing a real model.

### Local command run

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
```

Use this path when wiring a user-owned local benchmark command to EdgeEnv's explicit stdout contract.

Related docs:

- [Local Command Contract Guide](local-command-contract.md)
- [Local Real Benchmark Example Guide](local-real-benchmark-example.md)
- [Local Runner Design](local-runner-design.md)

### Resource metrics and sampler wrappers

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_wrapper.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_unavailable.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml
```

Current policy:

- resource metrics are optional secondary evidence
- missing resource metrics keeps a successful run valid
- malformed resource metrics creates a failed-run artifact
- resource metrics are not a comparability gate
- resource metrics are indexed in a rebuildable `resource_metric_index` for local lookup

Related docs:

- [Resource Metrics Design](resource-metrics-design.md)
- [Sampler Failure Policy](sampler-failure-policy.md)
- [Platform Sampler Design](platform-sampler-design.md)
- [Sampler Adapter API Design](sampler-adapter-api-design.md)
- [LocalRunner Sampler Wiring Design](local-runner-sampler-wiring-design.md)
- [Sampler Metadata Artifact Policy](sampler-metadata-artifact-policy.md)
- [Jetson Tegrastats Wrapper Guide](jetson-tegrastats-wrapper.md)
- [Registry Resource Query Design](registry-resource-query-design.md)
- [Resource Query Rehearsal](resource-query-rehearsal.md)

### Failed-run inspection workflow

```bash
edgeenv failed-runs list
edgeenv failed-runs show <run_id>
edgeenv failed-runs show <run_id> --log-chars 0
edgeenv failed-runs export <run_id> --output edgeenv-failed-run-<run_id>.zip
edgeenv failed-runs import edgeenv-failed-run-<run_id>.zip
```

Use this path after a local command failure or malformed metrics/resource metrics output. Failed runs are diagnostic artifacts, not successful registry records, so they are intentionally absent from `runs list`.

Related doc:

- [Failed Run Inspection Guide](failed-run-inspection.md)

### Registry and compare workflow

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv runs list
edgeenv runs show <run_id>
edgeenv runs resources list --metric memory_peak_mb
edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip
edgeenv runs import edgeenv-run-<run_id>.zip
edgeenv report compare <run_id_a> <run_id_b>
```

Expected same-condition example output:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
- latency_mean_ms: 18.0 ms -> 16.4 ms (delta -1.6 ms, -8.89%)
- latency_p50_ms: 17.6 ms -> 16.0 ms (delta -1.6 ms, -9.09%)
- latency_p95_ms: 20.5 ms -> 18.2 ms (delta -2.3 ms, -11.22%)
- latency_p99_ms: 22.0 ms -> 19.7 ms (delta -2.3 ms, -10.45%)
- throughput_fps: 55.5 fps -> 61.0 fps (delta +5.5 fps, +9.91%)
```

Related doc:

- [Compare Workflow Guide](compare-workflow-guide.md)

Metric deltas are supplemental and only appear for `Comparable: Yes` with `Mode: same-condition`; conditional and non-comparable reports intentionally suppress them.

## 4. HOW NOT — scope boundaries to preserve

Do not add these as hidden defaults or quickstart paths:

- OS, bootloader, GRUB, BCD, or Linux compatibility behavior
- VM, Docker, WSL, SSH, or cloud target execution
- Cloud DB, login/auth, web dashboard, public leaderboard
- Model upload server or dataset upload server
- Single-score model ranking
- Resource metrics as a required comparability field
- Platform-native sampler adapters inside `LocalRunner`

Do not break these contracts without an explicit migration plan:

- `result.json` schema version: `edgeenv.result.v1`
- failed-run artifact schema marker: `edgeenv.failed-run.v1`
- `.edgeenv/runs/<run_id>/` success artifact layout
- `.edgeenv/failed-runs/<run_id>/` diagnostic artifact layout
- `.edgeenv/runs.db` successful run registry semantics
- `.edgeenv/runs.db` `resource_metric_index` remains a rebuildable local lookup index, not canonical evidence
- `report compare` output labels: `Comparable`, `Mode`, `Reason`
- `failed-runs show` and `failed-runs import` read/copy failed artifacts only and must not insert into `runs.db`
- export/import must treat run artifacts as canonical evidence and `runs.db` as a rebuildable local index

Related portability design:

- [Export/Import Design](export-import-design.md)

## 5. WHERE — validation commands

Run these before considering a change ready:

```bash
python -m pytest -q
python -m inferedge_env.cli doctor
edgeenv doctor
python -m inferedge_env.cli profile validate examples/profiles/local_fake.yaml
python -m inferedge_env.cli profile validate examples/profiles/local.yaml
python -m inferedge_env.cli bench validate examples/benches/yolov8n_fire.yaml
python -m inferedge_env.cli bench validate examples/benches/local_template.yaml
python -m inferedge_env.cli bench validate examples/benches/local_runtime_adapter.yaml
python -m inferedge_env.cli bench validate examples/benches/local_compare_a.yaml
git diff --check
```

For install and entrypoint readiness:

```bash
bash scripts/smoke_entrypoints.sh
```

For Jetson source snapshot validation:

```bash
scripts/smoke_jetson_source_env.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
scripts/smoke_jetson_sampled_compare.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
scripts/smoke_jetson_sampled_conditional_compare.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
scripts/smoke_jetson_sampled_target_compare.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
scripts/smoke_jetson_sampled_bundle_handoff.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
scripts/smoke_jetson_sampled_bundle_handoff.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md --keep-artifacts
```

Notes:

- `scripts/smoke_entrypoints.sh` may need network access if build dependencies are not already available locally.
- `scripts/smoke_jetson_source_env.sh` intentionally uses `PYTHONPATH` and an existing Jetson Python environment instead of requiring editable install.
- `scripts/smoke_jetson_sampled_compare.sh` verifies that sampled resource evidence stays outside compare gates.
- `scripts/smoke_jetson_sampled_conditional_compare.sh` verifies runtime/provider Conditional mode and metric delta suppression with sampled evidence present.
- `scripts/smoke_jetson_sampled_target_compare.sh` verifies target-comparison mode and metric delta suppression with sampled evidence present.
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` verifies sampled successful-run bundle export/import and imported compare outcomes for same-condition, runtime-conditional, and target-conditional paths. Add `--bundle-summary-output <path>` when release rehearsal should also validate generated Markdown handoff output.
- [Jetson Sampled Bundle Portability Review](jetson-sampled-bundle-portability-review.md) records the decision to use a short Markdown handoff report for human review while keeping manifests/result artifacts canonical.
- [Bundle Report Generation Design](bundle-report-generation-design.md) defines and records the read-only `report bundle-summary` generator contract.
- [Jetson Bundle Summary Rehearsal](jetson-bundle-summary-rehearsal.md) records generated Markdown output from real imported Jetson sampled bundle runs.
- [Jetson Measurement Operations Checklist](jetson-operations-checklist.md) is the post-`v0.1.2` checklist for repeated Jetson measurement sessions, evidence retention, and failure triage.
- Tests should use `tmp_path` for `.edgeenv` data and must not pollute the repo root registry.
- GitHub Actions repeats the core readiness contract on Python 3.10 and 3.11.
- Before tagging a release, rerun or review [EdgeEnv MVP v1 Release Rehearsal](v1-release-rehearsal.md) and update the package version intentionally.

## 6. WHY — next work candidates

Recommended next work should stay in coherent bundles rather than tiny one-off PRs.

Good next bundles:

- **Install / Quickstart Resilience**: first v0.1.3 candidate; make editable install and entrypoint failures easier to triage for clean venv users.
- **README Quickstart Command Consistency**: second v0.1.3 candidate; reduce duplicated entry paths and clarify fake/local/compare/Jetson next steps.
- **Jetson operations rehearsal refresh**: update the operations checklist when repeated hardware runs reveal a new preflight check, artifact naming convention, or triage step.
- **Resource query UX refinement**: only if repeated use shows a need for JSON output, source summaries, or richer filters.
- **Release maintenance checklist**: fourth v0.1.3 candidate; collect clean-room, optional Jetson, tag, and GitHub Release steps for repeatable release work.
- **Release rehearsal refresh**: rerun the v1 user-flow rehearsal when the next code feature changes CLI behavior or artifact layout.

Avoid next bundles that jump straight into:

- Docker/WSL/SSH target implementation
- cloud sync or hosted dashboard
- public leaderboard
- model/dataset upload service
- composite performance score

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Keep branch names area-based and intuitive, such as `docs/...`, `runners/...`, `compare/...`, `ci/...`, or `packaging/...`.
- Finish each coherent work bundle with tests, PR, merge, and a clear next-step recommendation.
- If install smoke fails only because sandbox networking blocks build dependency lookup, rerun with proper network approval and record that in validation notes.
