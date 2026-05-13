# Evidence Contract Conformance Suite

This guide explains the first six-month roadmap phase: executable tests that prove InferEdgeEnv accepts valid evidence, rejects corrupt evidence, preserves failed-run artifacts, and keeps comparability judgement stable across export/import.

## Scope

The conformance suite protects public behavior, not private implementation details.

Covered contracts:

- `EDGEENV_METRICS_JSON=<json>` is required for local benchmark success.
- `EDGEENV_RESOURCE_METRICS_JSON=<json>` is optional but must be valid when present.
- Corrupt local evidence creates a failed-run artifact and does not update the successful-run registry.
- Successful runs write the required artifact files under `.edgeenv/runs/<run_id>/`.
- Resource metrics remain supplemental lookup evidence.
- `report compare` prints protocol-first judgement before metric deltas.
- Same-condition comparisons may print metric deltas.
- Conditional and non-comparable comparisons suppress metric deltas.
- Successful-run export/import preserves compare judgement.

## Current Test Entry Point

Run:

```bash
python -m pytest -q tests/test_evidence_contract_conformance.py
```

The suite uses temp EdgeEnv roots and must not write to the repo root `.edgeenv`.

## Cases

### Valid Local Evidence

The suite runs a deterministic local command that emits:

- primary benchmark metrics
- optional resource metrics

Expected result:

- successful registry row exists
- required run artifact files exist
- `runs resources list --json` can find supplemental resource metrics
- no failed-run artifact is created

### Corrupt Local Evidence

The suite covers:

- missing `EDGEENV_METRICS_JSON`
- malformed primary metrics JSON
- malformed resource metrics JSON

Expected result:

- command exits through the CLI failure path
- failed-run artifact files exist
- `failure.json` records the rejection reason
- stdout is preserved for debugging
- successful registry is not updated

### Compare Portability

The suite creates same-condition, runtime-conditional, and model-hash-different runs.

Expected result before and after successful-run export/import:

- same-condition stays `Comparable: Yes`
- runtime difference stays `Comparable: Conditional`
- model hash difference stays `Comparable: No`
- metric deltas appear only for same-condition comparisons

## Non-Goals

- No ranking or composite score.
- No resource metric compare gate.
- No Docker, WSL, SSH, VM, or remote target.
- No Jetson hardware requirement.
- No committed `.edgeenv/` output.

## Why This Matters

InferEdgeEnv is a run evidence registry and comparability checker. Its value is not that every benchmark command succeeds; its value is that accepted evidence is explicit, rejected evidence is preserved, and comparison claims remain honest after evidence is moved between workspaces.
