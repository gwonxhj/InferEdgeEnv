# EdgeEnv v0.1.4 Follow-up Note

## 1. WHAT — 이 문서가 정하는 것

`v0.1.4` 릴리스 이후 사용자가 무엇을 믿고 어디서 시작하면 되는지 짧게 정리한다.

`v0.1.4`는 새 target이나 leaderboard 릴리스가 아니다. `v0.1.3` first-user polish baseline 위에 evidence contract, real-command adapter template, schema policy, portfolio demo path, CLI error guidance, release quality gate를 묶은 release quality baseline이다.

## 2. CONTENTS — 현재 믿을 수 있는 기준

Release baseline:

- Version: `0.1.4`
- Tag: `v0.1.4`
- GitHub Release: [EdgeEnv v0.1.4](https://github.com/gwonxhj/InferEdgeEnv/releases/tag/v0.1.4)
- Release theme: release quality baseline
- Primary CLI: `edgeenv`
- Module entrypoint: `python -m inferedge_env.cli`

Validated capability:

- config-driven fake/local benchmark runs
- local `.edgeenv/runs/<run_id>/` result artifacts
- SQLite registry lookup
- successful-run export/import with registry rebuild
- failed-run diagnostic artifact inspection and portability
- comparability-first `report compare`
- optional resource metrics lookup with text and JSON output
- optional Jetson `tegrastats` sampled evidence
- read-only Markdown bundle summary for evidence handoff
- public evidence contract conformance tests for valid and corrupt local evidence
- copyable local benchmark adapter templates
- schema versioning policy for result, sampler, failed-run, export, and registry artifacts
- repeatable local release quality smoke

## 3. HOW — 어디서 시작하면 되는가

For a first local run:

```bash
python -m pip install -e ".[dev]"
edgeenv doctor
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

For connecting a real local command:

- Start with [Local Command Contract Guide](local-command-contract.md).
- Copy from [Local Real Benchmark Example Guide](local-real-benchmark-example.md) or `examples/scripts/adapter_template.py`.
- Emit exactly one `EDGEENV_METRICS_JSON=` line for primary benchmark metrics.
- Emit `EDGEENV_RESOURCE_METRICS_JSON=` only when optional resource metrics are valid JSON.

For comparing runs:

- Start with [Compare Workflow Guide](compare-workflow-guide.md).
- Trust `Comparable`, `Mode`, and `Reason` before reading any metric deltas.
- Metric deltas are supplemental and appear only for `Comparable: Yes` with `Mode: same-condition`.

For release/review work:

- Start with [Release Maintenance Checklist](release-maintenance-checklist.md).
- See [EdgeEnv v0.1.4 Release Rehearsal](v0.1.4-release-rehearsal.md) for the local quality gate that passed before this release.
- Use [Release Quality Gate Refresh](release-quality-gate-refresh.md) to understand what `scripts/smoke_release_quality_gate.sh` covers.

## 4. HOW NOT — 아직 하지 않는 것

`v0.1.4` does not add:

- OS, bootloader, GRUB, BCD, or Linux compatibility behavior
- VM, Docker, WSL, SSH, or cloud target execution
- cloud DB, login/auth, web dashboard, public leaderboard
- model upload server or dataset upload server
- single-score ranking or composite benchmark score
- resource metrics as comparability gates
- sampler metadata as registry source of truth
- schema migration for unknown future artifact versions

Do not present Jetson validation as remote runner support. Jetson evidence is collected by running EdgeEnv locally on the Jetson.

## 5. WHERE — 검증된 문서 흐름

Use this order when reviewing the release state:

1. [README](../README.md) — quickstart and project scope
2. [EdgeEnv v0.1.4 Release Rehearsal](v0.1.4-release-rehearsal.md) — release quality gate pass before version bump/tag
3. [Evidence Contract Conformance Suite](evidence-contract-conformance-suite.md) — valid/corrupt evidence contract tests
4. [Schema Versioning And Migration Policy](schema-versioning-migration-policy.md) — accepted schema markers and future-version rejection
5. [Portfolio Demo Path](portfolio-demo-path.md) — reviewer-facing demo route
6. [Release Maintenance Checklist](release-maintenance-checklist.md) — repeatable release gate
7. [Jetson Measurement Operations Checklist](jetson-operations-checklist.md) — repeated hardware measurement procedure

## 6. WHY — 배경 판단

The value of `v0.1.4` is release confidence. It turns the six-month quality roadmap into a repeatable gate: record evidence, reject corrupt evidence, preserve diagnostics, compare honestly, move bundles safely, and summarize handoff output without ranking.

The project boundary stays the same: EdgeEnv records local run evidence and judges comparability. It does not become an OS layer, remote execution system, cloud service, validation/decision layer, or leaderboard.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Release quality baseline notes should emphasize evidence portability and gate repeatability without implying new execution target support.
