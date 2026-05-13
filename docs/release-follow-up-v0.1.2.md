# EdgeEnv v0.1.2 Follow-up Note

## 1. WHAT — 이 문서가 정하는 것

`v0.1.2` 릴리스 이후 사용자가 무엇을 믿고 어디서 시작하면 되는지 짧게 정리한다.

이 문서는 changelog처럼 모든 commit을 나열하지 않는다. 릴리스 노트, 운영 체크리스트, 실제 Jetson 리허설을 하나의 사용자-facing 출발점으로 묶는다.

## 2. CONTENTS — 현재 믿을 수 있는 기준

Release baseline:

- Version: `0.1.2`
- Tag: `v0.1.2`
- Release title: `EdgeEnv MVP v1`
- Primary CLI: `edgeenv`
- Module entrypoint: `python -m inferedge_env.cli`

Validated capability:

- config-driven fake/local benchmark runs
- local `.edgeenv/runs/<run_id>/` result artifacts
- SQLite registry lookup
- successful-run export/import with registry rebuild
- failed-run diagnostic artifact inspection and portability
- comparability-first `report compare`
- optional resource metrics lookup
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

For local command integration:

- Start with [Local Command Contract Guide](local-command-contract.md).
- Then try [Local Real Benchmark Example Guide](local-real-benchmark-example.md).
- Use `EDGEENV_METRICS_JSON=` for primary benchmark metrics.
- Use `EDGEENV_RESOURCE_METRICS_JSON=` only as optional resource evidence.

For comparing runs:

- Start with [Compare Workflow Guide](compare-workflow-guide.md).
- Trust `Comparable`, `Mode`, and `Reason` before reading any metric deltas.
- Metric deltas are supplemental and appear only for `Comparable: Yes` with `Mode: same-condition`.

For moving evidence:

- Start with [Export/Import Design](export-import-design.md).
- Treat `.edgeenv/runs/<run_id>/result.json` and exported manifest/checksum entries as canonical evidence.
- Treat `runs.db` and `resource_metric_index` as rebuildable local lookup state.

For Jetson:

- Start with [Jetson Measurement Operations Checklist](jetson-operations-checklist.md).
- Use the source snapshot plus conda Python path when the Jetson does not have an editable install.
- Run Jetson commands on the Jetson shell. This is local execution on the device, not SSH target support.

## 4. HOW NOT — 아직 하지 않는 것

`v0.1.2` does not add:

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
2. [EdgeEnv MVP v1 Release Rehearsal](v1-release-rehearsal.md) — release/tag gate
3. [Release Maintenance Checklist](release-maintenance-checklist.md) — repeatable local, clean-room, optional Jetson, tag, and GitHub Release gate
4. [EdgeEnv MVP v1 Handoff Status](v1-handoff-status.md) — current capability snapshot
5. [Jetson Measurement Operations Checklist](jetson-operations-checklist.md) — repeated hardware measurement procedure
6. [Jetson Sampled Evidence Bundle Handoff](jetson-sampled-evidence-bundle-handoff.md) — real sampled bundle portability record
7. [Jetson Bundle Summary Rehearsal](jetson-bundle-summary-rehearsal.md) — generated Markdown handoff summary record

## 6. WHY — 배경 판단

The value of `v0.1.2` is not that it runs every possible edge runtime. The value is that it records local run evidence consistently, preserves artifacts across export/import, and refuses to compare numbers without checking benchmark protocol compatibility first.

The Jetson work closes the first hardware-backed loop: sampled resource evidence can travel with run bundles and remain supplemental after import. That makes the evidence easier to hand off without turning EdgeEnv into a remote execution system or leaderboard.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Keep follow-up notes short and user-facing; link to detailed rehearsal documents instead of duplicating every command and output.
