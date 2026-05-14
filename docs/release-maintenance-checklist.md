# EdgeEnv Release Maintenance Checklist

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This checklist defines the minimum release procedure before pinning `main` as the next tag.

It is not a feature design or automation spec. It compresses the release gate from `docs/v1-release-rehearsal.md` into a repeatable checklist covering local tests, optional clean-room rehearsal, optional Jetson smoke, tag creation, and GitHub Release publication.

## 2. CONTENTS — Files And Stack

Related files:

- `README.md` — user-facing Quickstart and Guide Map
- `pyproject.toml` — package version
- `docs/v1-release-rehearsal.md` — full release/tag gate and user-flow rehearsal
- `docs/readme-quickstart-cleanroom-rehearsal.md` — clean source archive + fresh venv validation record
- `docs/jetson-operations-checklist.md` — optional repeated Jetson operation procedure
- `docs/release-follow-up-v0.1.2.md` — previous release follow-up note format
- `docs/release-follow-up-v0.1.4.md` — latest release follow-up note format
- `docs/release-follow-up-v0.1.3.md` — previous release follow-up note format
- `docs/v0.1.3-candidate-plan.md` — v0.1.3 polish sequence
- `docs/v0.1.3-release-rehearsal.md` — v0.1.3 release rehearsal record
- `docs/release-quality-gate-refresh.md` — repeatable local/optional Jetson gate after the six-month quality roadmap
- `docs/v0.1.4-release-rehearsal.md` — v0.1.4 release quality gate rehearsal record
- `scripts/smoke_release_quality_gate.sh` — local-only release quality smoke

Stack: Markdown, pytest, Typer CLI, GitHub Actions, GitHub Release

## 3. HOW — Repeatable Release Procedure

### 1. Scope Freeze

- Confirm every PR intended for the tag has been merged into `main`.
- Leave work that should not be included in the tag on a separate branch.
- List only user-facing changes for the release note.
- Re-check non-goals: OS/VM/Docker/WSL/SSH/cloud/auth/dashboard/leaderboard/upload/composite ranking remain out of scope.

### 2. Local Gate

Align local `main`:

```bash
git switch main
git pull --ff-only
git status --short --branch
```

Required validation:

```bash
python -m pytest -q
git diff --check
python -m inferedge_env.cli doctor
edgeenv doctor
```

Run the repeatable local smoke:

```bash
scripts/smoke_release_quality_gate.sh
```

Use the skip option only when `python -m pytest -q` already passed for the same candidate environment and only CLI flow needs to be rechecked:

```bash
scripts/smoke_release_quality_gate.sh --skip-pytest
```

Success criteria:

- pytest passes.
- whitespace diff check passes.
- module entrypoint and console script both work.
- release quality smoke passes fake/local/resource/export-import/compare/bundle-summary/failed-run portability flows.
- `git status --short --branch` is clean and aligned with `main...origin/main`.

### 3. README Quickstart Smoke

`scripts/smoke_release_quality_gate.sh` automatically runs the local fake/resource/export-import path from this section. Use the manual commands only when step-by-step observation is needed.

Use a temporary root so the repo stays clean:

```bash
work_root=$(mktemp -d /private/tmp/inferedge-release-smoke.XXXXXX)
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv runs list --edgeenv-root "$work_root/.edgeenv"
edgeenv runs show <run_id> --edgeenv-root "$work_root/.edgeenv"
```

Check the resource query and export/import boundary:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv runs resources list --metric memory_peak_mb --json --edgeenv-root "$work_root/.edgeenv"
edgeenv runs export <run_id> --output "$work_root/run.zip" --edgeenv-root "$work_root/.edgeenv"
edgeenv runs import "$work_root/run.zip" --edgeenv-root "$work_root/imported.edgeenv"
edgeenv runs resources list --metric memory_peak_mb --json --edgeenv-root "$work_root/imported.edgeenv"
```

Success criteria:

- Successful runs are stored under `.edgeenv/runs/<run_id>/`.
- Imported registry rows are rebuilt from `result.json`.
- Resource query JSON shows `filters`, `sources`, `unit`, and `source` without creating ranking or comparability gates.

### 4. Compare And Report Smoke

`scripts/smoke_release_quality_gate.sh` automatically runs same-condition compare and bundle-summary flow. Use these commands when output wording needs manual review:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root "$work_root/.edgeenv"
edgeenv report bundle-summary --scenario same-condition:<run_id_a>:<run_id_b> --edgeenv-root "$work_root/.edgeenv" --output "$work_root/bundle-summary.md"
```

Success criteria:

- compare output starts with `Comparable`, `Mode`, and `Reason`.
- metric deltas appear only for `Comparable: Yes` with `Mode: same-condition`.
- bundle summary is read-only Markdown output and does not mutate run artifacts or exported zips.

### 5. Failed-Run Portability Smoke

`scripts/smoke_release_quality_gate.sh` automatically runs malformed resource metrics failed-run artifact, export/import, and imported failed-run inspection. Use these commands for manual triage:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs list --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs show <failed_run_id> --edgeenv-root "$work_root/.edgeenv" --log-chars 120
edgeenv failed-runs export <failed_run_id> --output "$work_root/failed-run.zip" --edgeenv-root "$work_root/.edgeenv"
edgeenv failed-runs import "$work_root/failed-run.zip" --edgeenv-root "$work_root/imported-failed.edgeenv"
edgeenv failed-runs show <failed_run_id> --edgeenv-root "$work_root/imported-failed.edgeenv" --log-chars 0
```

Success criteria:

- Malformed resource metrics are preserved as failed-run artifacts.
- Failed-run import only fills `.edgeenv/failed-runs/<run_id>/` and does not create or modify `runs.db`.

### 6. Optional Clean-Room Gate

When package metadata or README Quickstart changed, treat the clean-room gate as effectively required. Follow `docs/readme-quickstart-cleanroom-rehearsal.md` using a source archive and fresh venv, then confirm:

```bash
python -m pip install -e ".[dev]"
edgeenv doctor
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
```

### 7. Optional Jetson Gate

Run this gate when sampler/Jetson behavior changed or a new hardware-backed evidence baseline is needed. On a Jetson such as `nano01`, follow `docs/jetson-operations-checklist.md`.

Minimum check:

```bash
scripts/smoke_jetson_sampled_bundle_handoff.sh \
  --python /home/risenano01/miniconda3/envs/yolo_env/bin/python \
  --bundle-summary-output /tmp/InferEdgeEnv-jetson-bundle-summary.md \
  --bundle-summary-source-device nano01 \
  --keep-artifacts
```

Success criteria:

- EdgeEnv runs through local execution on the Jetson.
- sampled runs preserve optional resource/sampler evidence.
- exported/imported bundle compare and bundle summary preserve protocol-first judgement.
- The result is not described as SSH target support.

### 8. GitHub Gate

- Confirm PR checks pass on Python 3.10 and 3.11.
- Do not tag if any check failed, required check is pending, or high-risk diff is unreviewed.
- Tag the `main` commit, not an unmerged release branch.

### 9. Tag And Release

Confirm `pyproject.toml` version and tag name match, then tag:

```bash
git tag -a vX.Y.Z -m "EdgeEnv vX.Y.Z"
git push origin vX.Y.Z
```

Keep these sections in the GitHub Release body:

```text
Summary
- List only user-facing changes.

Validation
- python -m pytest -q
- python -m inferedge_env.cli doctor
- edgeenv doctor
- README smoke or clean-room rehearsal
- GitHub Actions python-3.10, python-3.11
- optional Jetson smoke, if run

Impact
- Explain what confidence was added to the local evidence loop.

Non-goals
- OS/VM/Docker/WSL/SSH/cloud/auth/dashboard/leaderboard/upload/composite ranking remain out of scope.
```

### 10. Post-Release Follow-Up

- Confirm the README top section and follow-up note point to the new tag.
- Leave a short next-work candidate in `docs/v1-handoff-status.md` or a new release follow-up note.
- After release, read the README Quickstart once from an external user's perspective before starting new feature work.

## 4. HOW NOT — What To Avoid

- Do not tag with failing tests, pending CI, or a dirty working tree.
- Do not commit generated `.edgeenv/`, zip bundles, models, engines, datasets, stdout/stderr artifacts, or benchmark evidence.
- Do not describe future work as currently supported behavior in release notes.
- Do not describe Jetson local execution validation as SSH or remote target support.
- Do not present resource metrics or bundle summaries as canonical evidence or ranking surfaces.
- Do not put metric deltas ahead of the protocol-first `report compare` judgement.

## 5. WHERE — Related Documents

- **V1 Release Rehearsal**: stores the full gate and observed output.
- **MVP Readiness Checklist**: tracks currently supported and unsupported behavior.
- **README Quickstart Clean-room Rehearsal**: validates install and entrypoints in a fresh environment.
- **Jetson Operations Checklist**: repeated operation procedure for hardware-backed sampled evidence.
- **Release Follow-up Note**: shows where users should start after a release.
- **Release Quality Gate Refresh**: defines the local smoke script and optional Jetson gate.

## 6. WHY — Background Judgment

An EdgeEnv release is not a race to add features. It freezes a trustworthy local-first evidence loop. The checklist must stay short enough to repeat, because repeatability is what keeps release notes accurate and unexaggerated.

This document is reusable after `v0.1.4` because it focuses on gates and judgement criteria rather than version-specific output.

## 7. LEARNED CAUTIONS — Learned Cautions

- The release maintenance checklist is a gate document, not automation. Create tags and releases only after tests, smoke, and CI actually pass.
