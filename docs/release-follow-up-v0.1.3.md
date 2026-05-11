# EdgeEnv v0.1.3 Follow-up Note

## 1. WHAT — 이 문서가 정하는 것

`v0.1.3` 릴리스 이후 사용자가 무엇을 믿고 어디서 시작하면 되는지 짧게 정리한다.

`v0.1.3`은 새 target이나 leaderboard 릴리스가 아니다. `v0.1.2` MVP v1 baseline 위에 첫 사용자 진입, resource query UX, 릴리스 반복 절차를 다듬은 first-user polish release다.

## 2. CONTENTS — 현재 믿을 수 있는 기준

Release baseline:

- Version: `0.1.3`
- Tag: `v0.1.3`
- GitHub Release: [EdgeEnv v0.1.3](https://github.com/gwonxhj/InferEdgeEnv/releases/tag/v0.1.3)
- Release theme: first-user polish release
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

## 3. HOW — 어디서 시작하면 되는가

For a first local run:

```bash
python -m pip install -e ".[dev]"
edgeenv doctor
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

For resource evidence lookup:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv runs resources list --metric memory_peak_mb
edgeenv runs resources list --metric memory_peak_mb --json
```

Resource metrics remain supplemental lookup evidence. They are not ranking inputs and do not affect comparability judgement.

For comparing runs:

- Start with [Compare Workflow Guide](compare-workflow-guide.md).
- Trust `Comparable`, `Mode`, and `Reason` before reading any metric deltas.
- Metric deltas are supplemental and appear only for `Comparable: Yes` with `Mode: same-condition`.

For release/review work:

- Start with [Release Maintenance Checklist](release-maintenance-checklist.md).
- See [EdgeEnv v0.1.3 Release Rehearsal](v0.1.3-release-rehearsal.md) for the local gate that passed before this release.

For first-user feedback:

- Start with [EdgeEnv v0.1.3 User Feedback Backlog](v0.1.3-user-feedback-backlog.md).
- Capture the first blocked README path before proposing new feature work.

## 4. HOW NOT — 아직 하지 않는 것

`v0.1.3` does not add:

- OS, bootloader, GRUB, BCD, or Linux compatibility behavior
- VM, Docker, WSL, SSH, or cloud target execution
- cloud DB, login/auth, web dashboard, public leaderboard
- model upload server or dataset upload server
- single-score ranking or composite benchmark score
- resource metrics as comparability gates
- sampler metadata as registry source of truth

Do not present Jetson validation as remote runner support. Jetson evidence is collected by running EdgeEnv locally on the Jetson.

## 5. WHERE — 검증된 문서 흐름

Use this order when reviewing the release state:

1. [README](../README.md) — quickstart and project scope
2. [EdgeEnv v0.1.3 User Feedback Backlog](v0.1.3-user-feedback-backlog.md) — first-user question intake before new feature work
3. [EdgeEnv v0.1.3 Release Rehearsal](v0.1.3-release-rehearsal.md) — checklist pass before version bump/tag
4. [Release Maintenance Checklist](release-maintenance-checklist.md) — repeatable release gate
5. [EdgeEnv v0.1.3 Candidate Plan](v0.1.3-candidate-plan.md) — completed first-user polish sequence
6. [EdgeEnv MVP v1 Handoff Status](v1-handoff-status.md) — current capability snapshot
7. [Jetson Measurement Operations Checklist](jetson-operations-checklist.md) — repeated hardware measurement procedure

## 6. WHY — 배경 판단

The value of `v0.1.3` is first-run confidence. It tightens the install/quickstart path, makes resource query output easier to inspect or script, and leaves a repeatable release gate for future maintainers.

The project boundary stays the same: EdgeEnv records local evidence and judges comparability. It does not become an OS layer, remote execution system, cloud service, or leaderboard.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Release follow-up notes should distinguish polish changes from new execution targets; `v0.1.3` improves usability without expanding target scope.
