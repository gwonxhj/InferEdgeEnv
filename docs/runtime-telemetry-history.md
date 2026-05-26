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
- `inferedge_env/result/telemetry_history.py` — rebuilds telemetry history from registered run artifacts
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
- Runtime telemetry `coverage`, when present, is preserved as evidence quality
  metadata. Missing coverage fields are treated as an evidence gap, not as a
  failed run or comparability failure.
- Runtime telemetry `history_seed`, when present with schema
  `inferedge-runtime-telemetry-history-seed-v1`, is copied into the history
  entry as `runtime_telemetry_history_seed`. EdgeEnv validates that the seed
  keeps `registry_owner=edgeenv`, `decision_owner=lab`,
  `production_monitoring=false`, and `missing_telemetry_is_failure=false`.
  If the seed includes a compact `run_config` snapshot, EdgeEnv validates the
  replay/comparability context shape and preserves it with the seed.
  This proves Runtime is only the telemetry evidence producer while EdgeEnv owns
  local history accumulation.

When present, EdgeEnv stores the payload in two places:

```text
.edgeenv/runs/<run_id>/result.json
.edgeenv/runs/<run_id>/runtime_telemetry.json
```

`result.json` keeps the run self-describing. The sidecar makes export/import and replay-oriented tooling easier without requiring a registry schema migration.

History export command:

```bash
edgeenv runs telemetry export-history --output /tmp/edgeenv-runtime-telemetry-history.json
```

Optional Orchestrator operation context can be attached when the feed comes
from InferEdgeOrchestrator's EdgeEnv handoff contract:

```bash
edgeenv runs telemetry export-history \
  --orchestrator-feed /tmp/orchestrator-edgeenv-feed.json \
  --output /tmp/edgeenv-runtime-telemetry-history.json
```

The feed schema is:

```text
inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1
```

EdgeEnv only accepts this feed when it explicitly declares
`not_a_regression_judgement=true` and `not_a_comparability_gate=true`. The feed
is then preserved under the matching history entry as
`orchestrator_operation_context`. It does not replace `runtime_telemetry`, does
not turn missing telemetry into a successful telemetry run, and does not change
the same-condition comparability gate.

EdgeEnv also requires the Orchestrator producer identity markers before
preserving the feed:

- `source_repository=InferEdgeOrchestrator`
- `artifact_role=orchestrator-supplemental-operation-context`
- `producer_contract=inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1`

Newer Orchestrator feeds can also declare `edgeenv_mapping_hint` fields. EdgeEnv
preserves these hints and validates them when present: Orchestrator may map only
supplemental candidate operation context to
`runtime_telemetry_context.candidate`, while EdgeEnv remains the owner of
`runtime_telemetry_context.history.telemetry_coverage`. When the feed declares
`candidate_context_required_fields`, EdgeEnv checks that the mapping hint and the
candidate context still include `run_id`, `telemetry_source`, `operation`, and
`resource` before the context can reach regression reports or Lab handoff
manifests.
If the feed includes device-local producer lineage under
`candidate_context.producer`, EdgeEnv also preserves that supplemental context.
The producer trace may include producer sources, per-task producer stages,
producer source mappings, and device-local event counts. EdgeEnv validates this
block when present. Device-local producer sources must remain present in both
the global source list and per-task source mapping, per-task stages must be
non-empty strings, and producer/device-local event counts must stay positive.
This does not make Orchestrator the comparability owner or runtime regression
owner.
For device-local handoff smokes, `inspect-history` can enforce that lineage with
`--require-device-local-producer`. The stricter check fails when the preserved
history artifact has no Orchestrator context, or when preserved
`candidate_context.producer` metadata lacks device-local producer sources,
producer source mappings, producer stage mappings, or positive event/task
counts. This remains an artifact integrity gate, not a deployment decision.
The same marker and mapping validation is applied when a selected run has no
`runtime_telemetry` and the Orchestrator context is preserved under
`missing_telemetry[].orchestrator_operation_context`; missing telemetry remains
an evidence gap, but the supplemental operation context stays traceable.

Replay validation command:

```bash
edgeenv runs telemetry inspect-history /tmp/edgeenv-runtime-telemetry-history.json
edgeenv runs telemetry inspect-history \
  /tmp/edgeenv-runtime-telemetry-history.json \
  --require-device-local-producer
```

The history artifact uses this top-level shape:

```json
{
  "schema_version": "edgeenv.runtime-telemetry-history.v1",
  "summary": {
    "registered_runs": 2,
    "telemetry_runs": 1,
    "history_seed_runs": 1,
    "history_seed_run_config_runs": 1,
    "missing_telemetry_runs": 1
  },
  "runs": [
    {
      "run_id": "run-20260522-000000-12345678",
      "runtime_telemetry": {
        "schema_version": "inferedge-runtime-telemetry-v1",
        "history_seed": {
          "schema_version": "inferedge-runtime-telemetry-history-seed-v1",
          "registry_owner": "edgeenv",
          "decision_owner": "lab",
          "production_monitoring": false,
          "missing_telemetry_is_failure": false,
          "run_config": {
            "batch": 1,
            "height": 224,
            "width": 224,
            "warmup": 1,
            "runs": 10,
            "timeout_ms": null,
            "input_mode": "dummy",
            "input_preprocess": "none",
            "power_mode": "unknown",
            "jetson_clocks": "unknown"
          },
          "points": [
            {
              "execution_sequence_id": 0,
              "telemetry_timestamp": "2026-05-22T00:00:00Z"
            }
          ]
        },
        "coverage": {
          "schema_version": "inferedge-runtime-telemetry-coverage-v1",
          "expected_fields": ["queue_depth", "gpu_temperature"],
          "observed_fields": ["gpu_temperature"],
          "missing_fields": ["queue_depth"],
          "coverage_ratio": 0.5,
          "comparability_owner": "edgeenv",
          "missing_telemetry_is_failure": false
        }
      },
      "runtime_telemetry_history_seed": {
        "schema_version": "inferedge-runtime-telemetry-history-seed-v1",
        "registry_owner": "edgeenv",
        "decision_owner": "lab",
        "production_monitoring": false,
        "missing_telemetry_is_failure": false
      },
      "orchestrator_operation_context": {
        "schema_version": "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1",
        "source_repository": "InferEdgeOrchestrator",
        "artifact_role": "orchestrator-supplemental-operation-context",
        "producer_contract": "inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1",
        "not_a_regression_judgement": true,
        "not_a_comparability_gate": true,
        "edgeenv_mapping_hint": {
          "copy_candidate_context_to": "runtime_telemetry_context.candidate",
          "operation_context_role": "supplemental",
          "coverage_summary_owner": "edgeenv",
          "coverage_summary_path": "runtime_telemetry_context.history.telemetry_coverage",
          "candidate_context_required_fields": [
            "run_id",
            "telemetry_source",
            "operation",
            "resource"
          ],
          "aiguard_evidence_candidates": [
            "runtime_queue_overload",
            "runtime_thermal_instability"
          ]
        }
      }
    }
  ],
  "missing_telemetry": [
    {
      "run_id": "run-without-telemetry",
      "reason": "runtime_telemetry_missing"
    }
  ]
}
```

This is a replay dataset seed. It records evidence gaps explicitly and does not turn missing telemetry into a failed benchmark run.

`inspect-history` is a read-only validation step for that seed artifact. It
checks the schema, summarizes replay run IDs, available telemetry fields,
execution sequence IDs, telemetry coverage metadata, and missing telemetry
evidence gaps. When `--require-device-local-producer` is set, it also confirms
that preserved Orchestrator operation context still includes device-local
producer lineage. It does not mutate the registry, change comparability
judgement, compute regression, or act as a monitoring alert.

Regression reports can attach this artifact as supplemental context:

```bash
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

Replay-to-regression smoke sequence:

```bash
edgeenv runs telemetry export-history \
  --output /tmp/edgeenv-runtime-telemetry-history.json
edgeenv runs telemetry inspect-history \
  /tmp/edgeenv-runtime-telemetry-history.json
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

The regression report records telemetry coverage and evidence gaps for the
baseline/candidate pair. It still calculates regression deltas only after the
normal same-condition comparability gate passes.

Runtime telemetry coverage context is copied into
`runtime_telemetry_context.<baseline|candidate>.telemetry_coverage` and, when
provided through the history artifact, `history_telemetry_coverage`. The history
artifact also exposes a producer-side `telemetry_coverage` summary with
`run_summaries` and `missing_field_runs`, so Lab or AIGuard consumers can reuse
EdgeEnv's replay summary instead of recomputing coverage gaps. This makes
coverage gaps visible downstream without allowing coverage to override
EdgeEnv's comparability-first regression policy.

Runtime `history_seed` context is preserved as
`runtime_telemetry_history_seed` in the exported history artifact and counted in
`summary.history_seed_runs`. It is a one-result replay seed for EdgeEnv history
accumulation, not a live telemetry stream or a production monitoring contract.
When Runtime provides `history_seed.run_config`, EdgeEnv counts it in
`summary.history_seed_run_config_runs` and exposes the run IDs from
`inspect-history` as replay context, not as a direct regression verdict. The
handoff gate also validates the preserved `run_config` field types so an
artifact cannot claim replay/comparability context while losing the execution
shape, repeat count, timeout, input mode, preprocess mode, power mode, or
Jetson clocks markers.
If the seed is malformed or tries to move registry/decision ownership away from
EdgeEnv/Lab, export fails rather than silently rewriting the ownership markers.

Replay edge cases are preserved as evidence context:

- If the compared candidate is missing runtime telemetry, the regression report
  records both `runtime_telemetry_missing_in_result` and the history
  `runtime_telemetry_missing` gap for that run.
- If the baseline/candidate `execution_sequence_id` order is inverted, EdgeEnv
  preserves both result-side and history-side sequence IDs. This does not
  change comparability or regression math; downstream diagnosis can treat it as
  deterministic review context.
- If an Orchestrator feed is attached, the regression report exposes it under
  the matching run's runtime telemetry context as supplemental operation
  evidence. Queue depth, deadline/fallback, and resource hints remain context
  for downstream review; EdgeEnv still owns only comparability-first regression
  analysis.

Optional AIGuard handoff:

```bash
python -m inferedge_aiguard.cli reason-edgeenv-regression \
  --input /tmp/edgeenv-regression.json
```

This is a cross-repo artifact handoff, not an EdgeEnv runtime dependency.
EdgeEnv owns the local history, comparability judgement, and regression report.
AIGuard may consume that report as deterministic warning evidence, while Lab
remains the final deployment decision owner.

Lab handoff manifest:

```bash
edgeenv report runtime-intelligence-handoff \
  --baseline-result .edgeenv/runs/<baseline_run_id>/result.json \
  --candidate-result .edgeenv/runs/<candidate_run_id>/result.json \
  --edgeenv-regression-report /tmp/edgeenv-regression.json \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output /tmp/edgeenv-runtime-intelligence-lab-handoff.json
```

This command writes an EdgeEnv producer-side manifest with source repository
mapping, artifact roles, and producer contract markers for the Runtime result,
EdgeEnv regression report, optional Orchestrator operation context, and
Lab-owned report boundary. When `runtime_telemetry_history_seed` entries are
present, the handoff validates their schema, `registry_owner=edgeenv`,
`decision_owner=lab`, non-production marker, and replay points before exposing
the seed count in `edgeenv_report_summary.history_seed_runs`. If seed
`run_config` snapshots are present, the handoff validates their field types and
preserves `edgeenv_report_summary.history_seed_run_config_runs` for Lab-side
traceability.
When preserved
Orchestrator context is present, the handoff also validates device-local
`candidate_context.producer` lineage, including per-task source/stage mappings
and positive producer/device-local event counts. It exposes the matching run IDs
in `edgeenv_report_summary.device_local_producer_context_run_ids`. The manifest also
includes `lab_bundle_alignment` metadata for Lab's Runtime Intelligence bundle:
required file keys, EdgeEnv-produced file keys, external AIGuard file keys,
source repository mapping, artifact roles, and producer contract names. It
intentionally does not produce AIGuard
`guard_analysis`; AIGuard remains a separate deterministic diagnosis provider
and Lab remains the deployment decision owner.

## 4. HOW NOT — What To Avoid

- Do not make runtime telemetry required for a successful run.
- Do not treat missing telemetry as a comparability failure.
- Do not treat missing telemetry coverage fields as a regression judgement.
- Do not add telemetry columns to `runs.db` before a query/report requirement is proven.
- Do not describe this as production observability, cloud monitoring, distributed tracing, or real-time data drift detection.
- Do not use telemetry to bypass the existing comparability-first regression policy.
- Do not treat `inspect-history` as a live health check; it only validates a local replay artifact.
- Do not use Orchestrator operation feed context as a substitute for Runtime telemetry or Lab deployment judgement.

## 5. WHERE — Role In The InferEdge Flow

Runtime produces execution and telemetry evidence. EdgeEnv preserves that evidence locally and keeps it portable. Lab remains the deployment decision owner. AIGuard may later consume deterministic warning evidence, but it does not own final deployment decisions.

Current flow:

```text
Runtime result
-> EdgeEnv result.json + runtime_telemetry.json
-> EdgeEnv runtime_telemetry_history_seed preservation
-> optional Orchestrator edgeenv_runtime_telemetry_feed context
-> EdgeEnv export/import replay seed
-> EdgeEnv runtime telemetry history artifact
-> EdgeEnv inspect-history replay validation
-> EdgeEnv comparability-first regression report with telemetry context
-> Lab deployment risk report
```

## 6. WHY — Background Judgment

Runtime regression monitoring needs more than a single latency number. It needs evidence about when, where, and under which runtime/resource conditions a result was produced. Storing telemetry as optional local evidence lets EdgeEnv deepen toward regression history without turning into a production monitoring platform.

The first implementation keeps compatibility by preserving unknown fields and keeping `edgeenv.result.v1` additive. The history export continues the same artifact-first policy: `runs.db` locates records, but `result.json` and optional telemetry evidence remain the source of truth.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
