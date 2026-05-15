# InferEdgeEnv Six-Month Quality Roadmap

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

This document turns the next six months of InferEdgeEnv work into a staged agentic execution plan.

InferEdgeEnv is already a usable local-first run evidence registry and comparability checker. The next work should improve confidence, onboarding, schema durability, and release discipline rather than expanding into remote runners, dashboards, leaderboards, or deployment decisions.

## Goal

Raise InferEdgeEnv from MVP-complete to portfolio-ready and reviewer-friendly.

The target outcome is that a new user or reviewer can answer:

- What exact benchmark evidence was recorded?
- Why is a run accepted or rejected?
- Can two runs be compared directly, conditionally, or not at all?
- Can evidence move through export/import without losing trust?
- Which CLI path should be used for fake, local, Jetson, and portfolio demo flows?

## Phase Order

Run these phases in order. Each phase should use a focused branch, pass tests, open a PR, merge, and then choose the next phase from this roadmap.

| Order | Branch | Work Package | Main Value |
|---|---|---|---|
| 1 | `evidence/contract-conformance-suite` | Evidence Contract Conformance Suite | Proves stdout metrics, artifacts, compare, and bundle contracts hold under good and bad inputs. |
| 2 | `examples/real-command-adapter-templates` | Real Command Adapter Templates | Gives users copyable templates for attaching real benchmark commands. |
| 3 | `schema/versioning-migration-policy` | Schema Versioning / Migration Policy | Makes result, sampler, registry, and bundle evolution explicit. |
| 4 | `docs/portfolio-demo-path` | Portfolio Demo Path | Freezes a clear end-to-end demo story for README, reviewers, and interviews. |
| 5 | `cli/error-message-polish` | CLI Error Message Polish | Improves first-user diagnosis when configs, metrics, bundles, or commands fail. |
| 6 | `release/quality-gate-refresh` | Release Quality Gate | Turns the above into repeatable smoke scripts and release checklist gates. |

## Completion Rule

For each phase:

1. Read the relevant `AGENTS.md` files before editing.
2. Keep the branch focused on one work package.
3. Add or update tests before calling the work complete.
4. Run the relevant local validation commands.
5. Run `git status` and remove unexpected generated files.
6. Push, open PR, wait for CI where available, merge, and return to `main`.
7. Update the next recommended step.

Do not merge if any relevant test fails.

## Phase 1: Evidence Contract Conformance Suite

### 1. WHAT

This phase builds a test and fixture suite that locks the evidence contracts InferEdgeEnv depends on: benchmark metrics stdout, optional resource metrics stdout, failed-run artifacts, successful-run artifacts, registry rows, compare judgement, export/import, and bundle summary.

### 2. CONTENTS

- `tests/` — conformance tests for good and bad contracts.
- `examples/scripts/` — deterministic scripts used by tests where useful.
- `docs/` — short guide explaining the conformance suite and what each case protects.
- `.edgeenv/` — must remain generated test output only, not committed.

Technology stack: pytest, Typer CLI runner, JSON/YAML fixtures, SQLite temp roots.

### 3. HOW

Start with fixtures for the smallest stable cases:

- valid `EDGEENV_METRICS_JSON=...`
- missing metrics line
- malformed metrics JSON
- malformed `EDGEENV_RESOURCE_METRICS_JSON=...`
- successful artifact write
- failed-run artifact write
- same-condition compare
- conditional compare
- no compare
- export/import preserving compare judgement

Prefer temp directories and existing CLI helpers over hand-written filesystem shortcuts. Tests should prove the public contract, not private implementation details.

### 4. HOW NOT

- Do not add new benchmark scoring or ranking rules — conformance protects comparability, not leaderboards.
- Do not make resource metrics part of the comparability gate — resource data remains supplemental evidence.
- Do not commit generated `.edgeenv/` artifacts — tests must isolate output in temp roots.
- Do not assert unstable timestamps or machine-specific paths — conformance tests should be deterministic.

### 5. WHERE

- Depends on `inferedge_env/runners/local.py`, `inferedge_env/result/`, `inferedge_env/registry/`, `inferedge_env/compare/`, and CLI commands.
- Supports README, examples, export/import, and release gates.
- Boundary: public CLI and artifact contract first; implementation details second.

### 6. WHY

InferEdgeEnv's value is evidence trust. A conformance suite makes that trust visible and prevents future changes from silently accepting corrupt metrics, losing failure evidence, or comparing incompatible runs.

### 7. LEARNED CAUTIONS

Use `$learn` to add newly discovered contract traps here or to the relevant area guide.

## Phase 2: Real Command Adapter Templates

### 1. WHAT

This phase gives users copyable adapter templates for connecting their own local benchmark command to InferEdgeEnv's explicit stdout contract.

### 2. CONTENTS

- `examples/scripts/adapter_template.py` — minimal user-owned benchmark adapter.
- `examples/scripts/local_runtime_adapter_demo.py` — richer deterministic wrapper if not already sufficient.
- `examples/benches/` — configs that call the templates.
- `examples/profiles/` — local profiles used by the templates.
- `docs/local-command-contract.md` and `docs/local-real-benchmark-example.md` — user guide updates.

Technology stack: Python subprocess, JSON stdout contract, YAML configs, local runner.

### 3. HOW

Keep templates realistic but deterministic. A user should be able to replace the inner command while preserving:

- primary metrics output
- optional resource metrics output
- stdout/stderr pass-through
- nonzero command exit behavior
- clear failure messages

Add tests that run the template through `edgeenv bench run` using temp roots.

### 4. HOW NOT

- Do not pretend EdgeEnv owns model correctness, dataset correctness, or runtime measurement loops — the adapter command owns benchmark semantics.
- Do not auto-parse arbitrary runtime logs — templates should emit explicit JSON lines.
- Do not introduce Docker, WSL, SSH, or remote execution as part of this phase.
- Do not require Jetson hardware for the generic template tests.

### 5. WHERE

- Depends on `LocalRunner`, config schema, examples, and README Quickstart.
- Feeds Portfolio Demo Path and Release Quality Gate.
- Boundary: adapter template bridges a user-owned command into EdgeEnv evidence recording.

### 6. WHY

The fastest way for a new user to trust InferEdgeEnv is to copy a working template, replace one inner command, and see artifacts, registry rows, and compare output appear.

### 7. LEARNED CAUTIONS

Use `$learn` when a template expectation is easy to misunderstand.

## Phase 3: Schema Versioning / Migration Policy

### 1. WHAT

This phase defines how InferEdgeEnv schemas evolve without breaking old evidence bundles or current compare behavior.

### 2. CONTENTS

- `docs/schema-versioning-migration-policy.md` — policy and compatibility matrix.
- `inferedge_env/result/schema.py` — result schema version if implementation is included.
- `inferedge_env/samplers/` — sampler metadata version if implementation is included.
- export/import manifest helpers — bundle manifest version if implementation is included.
- tests for version presence and import behavior.

Technology stack: Pydantic, JSON artifacts, SQLite registry rebuild, zip manifest/checksum validation.

### 3. HOW

Start with policy before implementation:

- identify current artifact types
- decide version fields and defaults
- define compatible, warning, and rejected imports
- document migration triggers
- add tests only after the policy is narrow

Implementation should be additive where possible.

### 4. HOW NOT

- Do not rewrite existing `result.json` semantics without explicit compatibility tests.
- Do not require registry DB columns for every future schema field.
- Do not import an unknown future schema silently.
- Do not treat schema migration as trust validation; checksum and manifest validation remain separate concerns.

### 5. WHERE

- Depends on result schema, artifact writer, export/import, sampler metadata, registry rebuild, and bundle summary.
- Supports long-term release maintenance.
- Boundary: schema versioning describes evidence shape, not whether a model should deploy.

### 6. WHY

Evidence bundles may outlive the current code. Versioning keeps old bundles interpretable and gives future changes a clear compatibility gate.

### 7. LEARNED CAUTIONS

Use `$learn` for schema fields that are easy to over-index or accidentally promote into compare gates.

## Phase 4: Portfolio Demo Path

### 1. WHAT

This phase freezes a repeatable reviewer-facing story: fake run, local command run, optional Jetson sampled evidence, export/import, compare, and bundle summary.

### 2. CONTENTS

- `docs/portfolio-demo-path.md` — canonical demo sequence.
- README Guide Map link.
- Optional smoke script that prints the demo commands without requiring Jetson.
- Optional captured sample output snippets.

Technology stack: CLI commands, examples, Markdown, optional Jetson notes.

### 3. HOW

Document the path in two lanes:

- local-only lane: fake/local command evidence that anyone can run
- Jetson lane: hardware-backed optional evidence when `jetson-device` or another Jetson is available

Keep each command copyable and state what files should appear.

### 4. HOW NOT

- Do not require Jetson for the main demo path.
- Do not describe sampled resource evidence as a ranking signal.
- Do not show conditional compare as a regression claim.
- Do not add marketing language that hides current non-goals.

### 5. WHERE

- Depends on examples, local command contract, export/import, compare, bundle summary, and release rehearsal docs.
- Supports README, portfolio README, and interview explanation.
- Boundary: demo path shows evidence handling, not production SaaS readiness.

### 6. WHY

Portfolio reviewers need a short path that demonstrates the core thesis: record evidence first, compare honestly, preserve artifacts, and avoid unsupported claims.

### 7. LEARNED CAUTIONS

Use `$learn` if a demo command is too environment-specific or easy to run from the wrong directory.

## Phase 5: CLI Error Message Polish

### 1. WHAT

This phase improves error messages for common first-user failures without changing core contracts.

### 2. CONTENTS

- `inferedge_env/cli.py` — user-facing error formatting.
- config validators — field-level validation messages.
- local runner — missing/malformed metrics, timeout, nonzero exit, working directory failures.
- export/import — checksum mismatch, unsafe path, duplicate run ID.
- tests that assert meaningful messages without overfitting full Rich output.

Technology stack: Typer, Rich, Pydantic, pytest CLI runner.

### 3. HOW

Polish the most likely failure paths first:

- config validation failure
- missing metrics line
- malformed metrics JSON
- malformed resource metrics JSON
- failed command
- import duplicate run ID
- checksum/path safety failure

Prefer concise action-oriented messages: what failed, why EdgeEnv rejected it, and where to look.

### 4. HOW NOT

- Do not hide failed-run artifacts behind generic exceptions.
- Do not turn every exception into a success with warning.
- Do not expose long stack traces for expected user errors.
- Do not assert exact ANSI styling in tests unless the style itself is contract.

### 5. WHERE

- Depends on CLI, config, runners, result writer, export/import, failed-run inspection docs, and tests.
- Supports first-user feedback backlog and release quality gate.
- Boundary: messages explain evidence contracts; they do not loosen those contracts.

### 6. WHY

Most external users will judge quality when something fails. Good errors make InferEdgeEnv feel deliberate instead of brittle.

### 7. LEARNED CAUTIONS

Use `$learn` when a confusing error path is discovered during clean-room or synthetic user rehearsals.

## Phase 6: Release Quality Gate

### 1. WHAT

This phase turns the improved confidence checks into repeatable release gates.

### 2. CONTENTS

- `scripts/smoke_*` — local smoke scripts if appropriate.
- `docs/release-maintenance-checklist.md` — updated gate.
- `docs/vX.Y.Z-release-rehearsal.md` — rehearsal records for the next release.
- CI workflow updates only if local scripts are stable and fast.

Technology stack: shell scripts, pytest, CLI smoke, optional GitHub Actions.

### 3. HOW

Keep the gate layered:

- fast local pytest
- CLI doctor and fake/local run smoke
- export/import/compare smoke
- bundle-summary smoke
- clean-room install smoke
- optional Jetson smoke

Document which gates are required and which are optional hardware checks.

### 4. HOW NOT

- Do not make Jetson required for every PR.
- Do not put slow or flaky benchmark loops in mandatory CI.
- Do not tag a release before rehearsal docs and tests pass.
- Do not let release scripts create committed `.edgeenv/` artifacts.

### 5. WHERE

- Depends on all previous phases.
- Supports GitHub Release notes, release follow-up notes, and future handoff.
- Boundary: release gate freezes confidence; it does not add product scope by itself.

### 6. WHY

After six months of polish, the project needs repeatability more than more features. A short, trusted gate lets future work move without re-litigating evidence quality every time.

### 7. LEARNED CAUTIONS

Use `$learn` for release checklist steps that are skipped or easy to mis-run.

## Suggested Six-Month Cadence

| Month | Focus | Expected Outcome |
|---|---|---|
| 1 | Evidence Contract Conformance Suite | Contract fixtures and tests make evidence failures explicit. |
| 2 | Real Command Adapter Templates | Users have copyable local adapter paths. |
| 3 | Schema Versioning / Migration Policy | Artifact evolution is documented and partially enforced. |
| 4 | Portfolio Demo Path | Reviewer-facing demo path is short and repeatable. |
| 5 | CLI Error Message Polish | First-user failures are clear and actionable. |
| 6 | Release Quality Gate | The polished flow becomes a repeatable release baseline. |

## Non-Goals

- OS, bootloader, GRUB, BCD, VM, WSL, Docker, or SSH target implementation.
- Cloud DB, login/auth, web dashboard, public leaderboard, model upload server, dataset upload server.
- Composite ranking or single-score model ordering.
- Replacing InferEdgeLab's validation / decision layer.
- Turning sampler/resource evidence into a compare gate.

## Next Branch

Start with:

```bash
git switch -c evidence/contract-conformance-suite
```

The first PR should add tests and fixtures that prove EdgeEnv accepts valid evidence, rejects corrupt evidence, preserves failed-run artifacts, and keeps comparability judgement stable across export/import.
