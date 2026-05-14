# EdgeEnv v0.1.5 Follow-up Note

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — What This Document Defines

This note summarizes the `v0.1.5` release baseline and the completion judgement for InferEdgeEnv v1.

`v0.1.5` is a v1-complete release baseline. It does not add a new execution target, cloud service, dashboard, or leaderboard. It freezes the current local-first evidence loop, portfolio summary, and release/README wording as the stable v1 submission state.

Completion judgement:

```text
InferEdgeEnv v1 is complete as a local-first run evidence registry and comparability checker.
Further work should be treated as v1.1+ extensions, not missing MVP scope.
```

## 2. CONTENTS — Trusted Baseline

Release baseline:

- Version: `0.1.5`
- Tag: `v0.1.5`
- GitHub Release: [EdgeEnv v0.1.5](https://github.com/gwonxhj/InferEdgeEnv/releases/tag/v0.1.5)
- Release theme: v1-complete evidence registry and comparability baseline
- Primary CLI: `edgeenv`
- Module entrypoint: `python -m inferedge_env.cli`

Validated capability:

- config-driven fake/local benchmark runs
- local `.edgeenv/runs/<run_id>/` result artifacts
- SQLite registry lookup and resource metric lookup
- successful-run export/import with registry rebuild
- failed-run diagnostic artifact inspection and portability
- comparability-first `report compare`
- same-condition metric deltas only after comparability judgement
- conditional/no-comparison delta suppression
- optional resource metrics and sampler metadata as supplemental evidence
- optional Jetson `tegrastats` sampled evidence through local Jetson execution
- read-only Markdown bundle summary for evidence handoff
- public evidence contract conformance tests
- copyable local benchmark adapter templates
- schema versioning policy for result, sampler, failed-run, export, and registry artifacts
- portfolio summary and demo path for reviewer onboarding
- repeatable local release quality smoke

## 3. HOW — Where To Start

For a first local run:

```bash
python -m pip install -e ".[dev]"
edgeenv doctor
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

For a reviewer:

- Start with [InferEdgeEnv Portfolio Summary](portfolio_summary.md).
- Then follow [Portfolio Demo Path](portfolio-demo-path.md).
- Use [Compare Workflow Guide](compare-workflow-guide.md) before interpreting metric deltas.
- Use [Export/Import Design](export-import-design.md) and [Schema Versioning And Migration Policy](schema-versioning-migration-policy.md) for evidence portability and compatibility boundaries.

For release/review work:

- Start with [Release Maintenance Checklist](release-maintenance-checklist.md).
- See [EdgeEnv v0.1.5 Release Rehearsal](v0.1.5-release-rehearsal.md) for the clean-room release candidate gate.
- Use [Release Quality Gate Refresh](release-quality-gate-refresh.md) to understand what `scripts/smoke_release_quality_gate.sh` covers.

## 4. HOW NOT — What This Release Does Not Add

`v0.1.5` does not add:

- OS, bootloader, GRUB, BCD, or Linux compatibility behavior
- VM, Docker, WSL, SSH, or cloud target execution
- cloud DB, login/auth, web dashboard, public leaderboard
- model upload server or dataset upload server
- deployment decision logic
- single-score ranking or composite benchmark score
- resource metrics as comparability gates
- sampler metadata as registry source of truth
- schema migration for unknown future artifact versions

Do not present Jetson validation as remote runner support. Jetson evidence is collected by running EdgeEnv locally on the Jetson.

## 5. WHERE — Verified Documentation Path

Use this order when reviewing the release state:

1. [InferEdgeEnv Portfolio Summary](portfolio_summary.md) — v1 role and boundary
2. [README](../README.md) — quickstart and project scope
3. [EdgeEnv v0.1.5 Release Rehearsal](v0.1.5-release-rehearsal.md) — clean-room release candidate gate
4. [Portfolio Demo Path](portfolio-demo-path.md) — reviewer-facing demo route
5. [Evidence Contract Conformance Suite](evidence-contract-conformance-suite.md) — valid/corrupt evidence contract tests
6. [Schema Versioning And Migration Policy](schema-versioning-migration-policy.md) — accepted schema markers and future-version rejection
7. [Release Maintenance Checklist](release-maintenance-checklist.md) — repeatable release gate
8. [Jetson Measurement Operations Checklist](jetson-operations-checklist.md) — repeated hardware measurement procedure

## 6. WHY — Background Judgment

The value of `v0.1.5` is completion clarity. It aligns the release tag, README first screen, Env portfolio summary, and top-level InferEdge positioning around one message:

```text
InferEdgeEnv records whether benchmark evidence can be trusted and compared.
```

The project boundary stays the same: EdgeEnv records local run evidence and judges comparability. It does not become an OS layer, remote execution system, cloud service, validation/decision layer, operation-control layer, or leaderboard.

## 7. ⚠️ LEARNED CAUTIONS — Learned Cautions

- Completion wording should freeze the v1 boundary without implying new execution target support.
