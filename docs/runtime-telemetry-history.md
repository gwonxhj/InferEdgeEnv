# Runtime Telemetry History Seed

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This document defines the first EdgeEnv ingestion point for InferEdge Runtime telemetry.

EdgeEnv does not become a cloud monitoring service. It records runtime telemetry as local-first run evidence so later work can build reproducible history, replay datasets, comparability checks, and runtime regression analysis from artifacts.

## 2. CONTENTS — Files And Stack

Related files:

- `inferedge_env/runners/local.py` — parses optional `EDGEENV_RUNTIME_TELEMETRY_JSON=` stdout evidence
- `inferedge_env/runners/base.py` — carries optional runtime telemetry through `RunnerResult`
- `inferedge_env/result/schema.py` — preserves optional telemetry in `edgeenv.result.v1`
- `inferedge_env/result/writer.py` — writes telemetry to `result.json` and `runtime_telemetry.json`
- `inferedge_env/result/exporter.py` — exports/imports the optional sidecar with manifest validation
- `inferedge_env/cli.py` — shows stored/omitted telemetry status and `runs show` payload
- `docs/local-command-contract.md` — stdout contract for local commands
- `docs/export-import-design.md` — portable evidence bundle contract

Stack: JSON artifacts, Pydantic result validation, local filesystem evidence, zip manifest checksums

## 3. HOW — Current Contract

Local benchmark commands may emit:

```text
EDGEENV_RUNTIME_TELEMETRY_JSON=<json object>
```

The payload is intentionally additive and minimally validated:

- it must be a JSON object
- `schema_version`, when present, must be a string
- unknown telemetry fields are preserved instead of normalized into registry columns

When present, EdgeEnv stores the payload in two places:

```text
.edgeenv/runs/<run_id>/result.json
.edgeenv/runs/<run_id>/runtime_telemetry.json
```

`result.json` keeps the run self-describing. The sidecar makes export/import and replay-oriented tooling easier without requiring a registry schema migration.

## 4. HOW NOT — What To Avoid

- Do not make runtime telemetry required for a successful run.
- Do not treat missing telemetry as a comparability failure.
- Do not add telemetry columns to `runs.db` before a query/report requirement is proven.
- Do not describe this as production observability, cloud monitoring, distributed tracing, or real-time data drift detection.
- Do not use telemetry to bypass the existing comparability-first regression policy.

## 5. WHERE — Role In The InferEdge Flow

Runtime produces execution and telemetry evidence. EdgeEnv preserves that evidence locally and keeps it portable. Lab remains the deployment decision owner. AIGuard may later consume deterministic warning evidence, but it does not own final deployment decisions.

Current flow:

```text
Runtime result
-> EdgeEnv result.json + runtime_telemetry.json
-> EdgeEnv export/import replay seed
-> future telemetry history/replay/regression analysis
-> Lab deployment risk report
```

## 6. WHY — Background Judgment

Runtime regression monitoring needs more than a single latency number. It needs evidence about when, where, and under which runtime/resource conditions a result was produced. Storing telemetry as optional local evidence lets EdgeEnv deepen toward regression history without turning into a production monitoring platform.

The first implementation keeps compatibility by preserving unknown fields and keeping `edgeenv.result.v1` additive. Future phases can add history accumulation and replay validation using the same artifact-first policy.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
