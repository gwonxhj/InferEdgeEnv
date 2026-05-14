# Release Quality Gate Refresh

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Evidence Contract Conformance Suite, Real Command Adapter Templates, Schema Versioning, Portfolio Demo Path, CLI Error Message Polish 이후의 release gate를 반복 가능한 형태로 정리한다.

결정: 필수 local gate는 `scripts/smoke_release_quality_gate.sh`로 자동화하고, Jetson sampled evidence gate는 기존 `scripts/smoke_jetson_sampled_bundle_handoff.sh`를 optional hardware gate로 유지한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_release_quality_gate.sh` — local-only release quality smoke
- `scripts/smoke_entrypoints.sh` — install/entrypoint/pytest smoke
- `scripts/smoke_jetson_sampled_bundle_handoff.sh` — optional Jetson sampled bundle handoff smoke
- `docs/release-maintenance-checklist.md` — tag/GitHub Release checklist source
- `docs/portfolio-demo-path.md` — reviewer-facing demo path
- `docs/cli-error-message-polish.md` — expected failure message policy
- `docs/evidence-contract-conformance-suite.md` — evidence contract test coverage
- `docs/schema-versioning-migration-policy.md` — schema compatibility gate
- `.github/workflows/readiness.yml` — PR/main CI readiness gate

기술 스택: Bash, Typer CLI, pytest, local filesystem artifacts, SQLite registry, zip export/import, optional Jetson `tegrastats`

## 3. HOW — refreshed gate

### Required local gate

Run from repo root after editable install is available:

```bash
scripts/smoke_release_quality_gate.sh
```

If `python -m pytest -q` already passed in the same environment and only the CLI smoke needs replay:

```bash
scripts/smoke_release_quality_gate.sh --skip-pytest
```

To keep generated artifacts for inspection:

```bash
scripts/smoke_release_quality_gate.sh --keep-artifacts
```

The smoke validates:

- module and console `doctor`
- `git diff --check`
- full pytest unless `--skip-pytest` is passed
- representative profile/config validation
- fake run artifact and registry path
- local adapter run
- resource metrics query before and after successful-run export/import
- same-condition `report compare` with metric delta
- read-only `report bundle-summary`
- malformed resource metrics failed-run artifact
- failed-run export/import without creating `runs.db`
- no ranking tables, leaderboard sections, or composite score fields in bundle summary

Generated artifacts are written under a temporary root such as:

```text
/private/tmp/inferedge-release-quality.<suffix>
```

The script deletes only generated roots matching its own temp prefix unless `--keep-artifacts` is set.

### Optional install/entrypoint gate

Use when packaging metadata, README install instructions, or console entrypoints changed:

```bash
bash scripts/smoke_entrypoints.sh
```

This may require network access if editable install dependencies are not already available locally.

### Optional Jetson hardware gate

Use when sampler, Jetson docs, bundle handoff, or hardware-backed evidence baseline changed:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

This remains optional because the main release gate must not require Jetson hardware for every PR.

## 4. HOW NOT — 피해야 할 함정

- Do not tag if the local quality smoke, pytest, or CI fails.
- Do not make Jetson hardware mandatory for every release candidate.
- Do not commit generated `.edgeenv/`, zip bundles, `bundle-summary.md`, stdout/stderr logs, models, engines, or datasets.
- Do not add remote SSH, Docker, WSL, cloud, dashboard, upload, leaderboard, or composite ranking behavior to the release gate.
- Do not treat bundle-summary as canonical evidence; it remains a read-only handoff report.
- Do not use `--skip-pytest` unless full pytest already passed in the same candidate environment.

## 5. WHERE — 다른 설계와의 관계

- **Release Maintenance Checklist**: now points to the local quality smoke as the repeatable required gate.
- **CI Readiness Workflow**: remains the PR/main safety net on Python 3.10 and 3.11.
- **Portfolio Demo Path**: local smoke exercises the same fake/local/compare/export-import/bundle-summary story.
- **CLI Error Message Polish**: local smoke checks failed-run guidance appears during malformed resource metrics.
- **Jetson Operations Checklist**: optional hardware gate remains separate.

## 6. WHY — 배경 판단

The six-month quality roadmap ends with repeatability. A release gate should be short enough to run, strict enough to catch evidence contract drift, and scoped enough not to imply unsupported product features.

`scripts/smoke_release_quality_gate.sh` freezes the local-first evidence loop as a release baseline: record evidence, reject corrupt evidence, compare honestly, move bundles safely, and summarize handoff output without ranking.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
