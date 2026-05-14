# Cross-Repo Positioning Review

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Records

This document records the May 2026 review of adjacent InferEdge repositories and the small positioning updates reflected back into InferEdgeEnv.

The goal is not to add a feature. The goal is to keep InferEdgeEnv's product boundary consistent with the rest of the portfolio.

## 2. CONTENTS — Repositories Checked

Repositories reviewed:

- `InferEdge`
- `InferEdgeForge`
- `InferEdge-Runtime`
- `InferEdgeLab`
- `InferEdgeAIGuard`
- `InferEdgeOrchestrator`

Documents checked included each repository's README and the available architecture, integration, pipeline, or portfolio notes that mention InferEdgeEnv, evidence, comparability, validation, or deployment decisions.

## 3. HOW — Findings

The Forge, Runtime, Lab, and AIGuard READMEs are aligned with the current Env positioning:

```text
InferEdgeEnv is a local-first run evidence registry and comparability checker.
InferEdgeLab is the validation / decision layer.
InferEdgeEnv is the run evidence registry / comparability layer.
```

The top-level InferEdge README and pipeline map still use the older supporting-repository phrasing around local environment and reproducibility. That placement is acceptable because Env is not part of the pinned Core 4 validation path, but Env should describe the support role more precisely as benchmark run evidence recording and comparability checking.

InferEdgeOrchestrator adds a separate boundary: it is the post-deployment operation-control layer. It may consume upstream evidence or decision outputs, but it owns scheduling, load shedding, telemetry, and runtime coordination after deployment. Env should not be described as that layer.

## 4. HOW NOT — Wording To Avoid

Do not describe InferEdgeEnv as:

- a generic environment helper
- an InferEdgeLab replacement
- a deployment decision engine
- an operation-control or scheduler layer
- a live telemetry system
- a public benchmark leaderboard

## 5. WHERE — Env Updates Made

The review is reflected in:

- `README.md` relation section
- `docs/ko/README.md` project-position section

No schema, CLI contract, compare output, registry layout, or artifact contract changed.

## 6. WHY — Product Boundary

The safest portfolio wording is:

```text
InferEdge validates whether a model is deployable.
InferEdgeEnv records whether benchmark evidence can be trusted and compared.
```

That keeps Env useful without overlapping Lab's validation/decision role or Orchestrator's post-deployment operation-control role.

## 7. LEARNED CAUTIONS

- Cross-repo README wording can drift even when the implementation contract is stable; Env should keep its canonical definition centered on evidence registry and comparability, not generic environment setup.
