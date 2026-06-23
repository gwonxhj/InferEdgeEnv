# EdgeEnv

> Language: English | [한국어](docs/ko/README.md)

InferEdgeEnv is a local-first run evidence registry and comparability checker for Edge AI inference benchmark results. The user-facing CLI command is `edgeenv`.

## Start Here for v0.1.5

`v0.1.5` is the current v1-complete release baseline. InferEdgeEnv v1 is complete as a local-first run evidence registry and comparability checker; later work should be treated as v1.1+ extensions, not missing MVP scope. The first path is:

1. Install and run `doctor`.
2. Record a deterministic fake run.
3. Try a local command run.
4. Compare only after EdgeEnv checks comparability.
5. Use Jetson docs only when you are ready to run EdgeEnv locally on the Jetson shell.

Validated scope: fake/local benchmark recording, artifact storage, registry lookup, export/import, comparability reports, optional resource metrics, read-only bundle summaries, and Jetson `tegrastats` sampled evidence through local execution on Jetson.

Start with [Quickstart](#quickstart). If install fails while pip is fetching build dependencies, check [Install And Quickstart Resilience](docs/install-quickstart-resilience.md) before treating it as an EdgeEnv runtime failure.

If the first path is confusing or blocked, open a [README Quickstart feedback issue](https://github.com/gwonxhj/InferEdgeEnv/issues/new?template=readme-quickstart-feedback.md) and use the [first-user feedback backlog](docs/v0.1.3-user-feedback-backlog.md) to classify the first blocked step.

After the first fake run, choose the next path:

- Connect your command: [Local Command Contract Guide](docs/local-command-contract.md)
- Compare two runs: [Compare Workflow Guide](docs/compare-workflow-guide.md)
- Repeat Jetson measurements: [Jetson Measurement Operations Checklist](docs/jetson-operations-checklist.md)

## Problem

Edge inference results are easy to record but hard to compare honestly. A latency number is only meaningful when model identity, input shape, precision, batch size, warmup/repeat protocol, and preprocess/postprocess boundaries are known.

EdgeEnv focuses on recording benchmark evidence locally and judging whether two runs are directly comparable, conditionally comparable, or not comparable.

## Role Boundary At A Glance

| Area | EdgeEnv owns | EdgeEnv does not own |
| --- | --- | --- |
| Run evidence registry | Stores local artifacts, SQLite registry rows, portable bundles, telemetry history, and replay metadata | Replace Runtime execution or become a production telemetry database |
| Comparability judgement | Checks same-condition, runtime-comparison, target-comparison, and protocol-mismatch boundaries before metric deltas | Rank every model with a single score or bypass benchmark protocol checks |
| Runtime regression evidence | Computes latency/resource regression only after the comparability gate passes and emits JSON/Markdown evidence | Make deployment decisions, overwrite Lab `deployment_decision`, or act as AIGuard diagnosis |
| Operation context handoff | Preserves Runtime/Orchestrator supplemental telemetry, producer lineage, and Lab handoff markers as traceability evidence | Become a scheduler, cloud control plane, production observability platform, or remote execution proof |

## What EdgeEnv Is Not

EdgeEnv is not:

- An OS, bootloader, GRUB, BCD, or Linux compatibility layer
- A VM, Docker, WSL, or cloud target manager
- A cloud database, login/auth system, web dashboard, or public leaderboard
- A model upload server or dataset upload server
- A single-score ranking system for all models

## Quickstart

Install and confirm both entrypoints:

```bash
python -m pip install -e ".[dev]"
python -m inferedge_env.cli doctor
edgeenv doctor
```

### 1. Record a Fake Run

Run the deterministic fake benchmark first. This checks the CLI, config schema, artifact writer, and registry without executing a real model.

```bash
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
```

Use the `Run ID` printed by `bench run`, or copy it from `edgeenv runs list`, when replacing `<run_id>`.

### 2. Record a Local Command Run

Then try the local runner examples. These execute small deterministic Python commands on the current machine.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_echo_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
```

The local target executes `command` on the current machine and reads an explicit `EDGEENV_METRICS_JSON=` line from stdout. Local commands may also emit optional `EDGEENV_RESOURCE_METRICS_JSON=`, `EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON=`, or `EDGEENV_RUNTIME_TELEMETRY_JSON=` lines for supplemental evidence. `bench run` reports whether resource metrics and runtime telemetry were stored or omitted.

To connect your own benchmark command, start from `examples/scripts/adapter_template.py` when wrapping an existing command, or `examples/scripts/local_benchmark_template.py` when writing the benchmark loop directly. Then review the adapter pattern in [Local Real Benchmark Example Guide](docs/local-real-benchmark-example.md).

### 3. Compare Two Runs

Compare two registered runs after you have at least two successful run IDs. EdgeEnv prints the comparability judgement before any metric delta.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv runs list
edgeenv report compare <run_id_a> <run_id_b>
```

For the full flow, see [Compare Workflow Guide](docs/compare-workflow-guide.md).
The guide also links small committed runtime regression replay fixtures under
`examples/regression/` for downstream AIGuard/Lab handoff checks. The fixture
matrix covers same-condition regression, runtime-comparison, target-comparison,
protocol-mismatch, telemetry-gap, and replay-sequence context without requiring
a live device. Use `examples/regression/fixture_matrix.json` as the
machine-readable index for which fixture represents each mode and whether
regression deltas are allowed.

### 4. Optional Resource And Sampler Evidence

Sampler wrapper examples show the first integration boundary for optional resource evidence.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_wrapper.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_unavailable.yaml
```

On Jetson, use the `tegrastats` wrapper path from the repo root:

```bash
edgeenv bench run --target examples/profiles/jetson_nano_local.yaml --config examples/benches/jetson_tegrastats_local.yaml
```

For the sampler adapter lifecycle path on Jetson, use the sampled local profile
and inspect sampler metadata without opening artifact files manually:

```bash
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml
edgeenv runs sampler show <run_id>
```

If a sampler is unavailable, the wrapper should omit `EDGEENV_RESOURCE_METRICS_JSON=` and preserve the successful primary benchmark run. If a wrapper emits malformed resource metrics, EdgeEnv writes a failed-run artifact and does not update the registry:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_sampler_malformed_resource.yaml
edgeenv failed-runs list
edgeenv failed-runs show <failed_run_id>
edgeenv failed-runs export <failed_run_id> --output edgeenv-failed-run-<failed_run_id>.zip
edgeenv failed-runs import edgeenv-failed-run-<failed_run_id>.zip
```

### 5. Inspect Evidence

`runs show` reads the result artifact and includes resource, runtime operation,
or runtime telemetry evidence when the local command emits it:

```bash
edgeenv runs show <run_id>
edgeenv runs resources list --metric memory_peak_mb
edgeenv runs resources list --metric memory_peak_mb --json
edgeenv runs telemetry export-history --output /tmp/edgeenv-runtime-telemetry-history.json
```

```json
{
  "resource_metrics": {
    "energy_j": 31.7,
    "memory_mean_mb": 420.5,
    "memory_peak_mb": 512.0,
    "power_mean_w": 8.2,
    "power_peak_w": 11.4,
    "source": "example-script",
    "temperature_peak_c": 72.0
  },
  "runtime_operation_summary": {
    "health_reason": "completed",
    "source": "inferedge-runtime"
  },
  "runtime_telemetry": {
    "collection_mode": "single_result_export",
    "resource": {
      "telemetry_source": "runtime-result"
    },
    "schema_version": "inferedge-runtime-telemetry-v1"
  }
}
```

The fake target uses `FakeRunner`, so it does not execute a real model.
Local benchmark configs may set `timeout_seconds`, `working_directory`, and uppercase `extra_env` keys for controlled command execution.
The Python package is `inferedge_env`; the user-facing CLI command remains `edgeenv`.

## Guide Map

English representative path:

- [InferEdgeEnv Portfolio Summary](docs/portfolio_summary.md) — 30-second role, boundary, and reviewer path for this repository
- [Documentation Language Guide](docs/language.md) — choose the English representative path or Korean entry path
- [EdgeEnv v0.1.5 Follow-up Note](docs/release-follow-up-v0.1.5.md) — current v1-complete release baseline and trusted starting point
- [Portfolio Demo Path](docs/portfolio-demo-path.md) — reviewer-facing fake/local/compare/export-import/bundle-summary demo path
- [Local Command Contract Guide](docs/local-command-contract.md) — how to connect your own local benchmark command
- [Runtime Telemetry History Seed](docs/runtime-telemetry-history.md) — optional runtime telemetry evidence ingestion and replay seed boundary
- [Compare Workflow Guide](docs/compare-workflow-guide.md) — how to judge comparability before reading metric deltas
- [한국어 Runtime Regression Monitor Quick Guide](docs/ko/runtime-regression-monitor.md) — Korean quick guide for comparability-first runtime regression evidence
- [Export/Import Design](docs/export-import-design.md) — portable evidence bundle contract
- [Schema Versioning And Migration Policy](docs/schema-versioning-migration-policy.md) — evidence compatibility and future-version rejection policy
- [Release Maintenance Checklist](docs/release-maintenance-checklist.md) — repeatable local, clean-room, optional Jetson, tag, and GitHub Release gate

Operational records:

- [EdgeEnv v0.1.5 Release Rehearsal](docs/v0.1.5-release-rehearsal.md) — clean-room source archive release gate and patch-candidate judgement
- [EdgeEnv v0.1.4 Follow-up Note](docs/release-follow-up-v0.1.4.md) — previous release quality baseline
- [EdgeEnv v0.1.4 Bilingual Docs Sanity Sweep](docs/v0.1.4-bilingual-docs-sanity-sweep.md) — README, Korean README, and representative docs reading-path check
- [EdgeEnv v0.1.4 Release Rehearsal](docs/v0.1.4-release-rehearsal.md) — release quality gate run before the v0.1.4 candidate
- [EdgeEnv v0.1.4 Post-release Sanity Sweep](docs/v0.1.4-post-release-sanity-sweep.md) — post-release check of README, follow-up note, and GitHub Release wording
- [Release Quality Gate Refresh](docs/release-quality-gate-refresh.md) — local release smoke script and optional Jetson gate after the six-month quality roadmap
- [README Quickstart Clean-room Rehearsal](docs/readme-quickstart-cleanroom-rehearsal.md) — fresh source archive and venv validation of the README path
- [Jetson Measurement Operations Checklist](docs/jetson-operations-checklist.md) — repeated hardware measurement procedure
- [Jetson Sampled Evidence Bundle Handoff](docs/jetson-sampled-evidence-bundle-handoff.md) — sampled bundle export/import and imported compare validation
- [EdgeEnv MVP v1 Handoff Status](docs/v1-handoff-status.md) — current capability snapshot and future-work entry points
- [First-user Feedback Backlog](docs/v0.1.3-user-feedback-backlog.md) — v0.1.5 candidate usability observations before new feature work

Design references:

- [InferEdgeEnv Six-Month Quality Roadmap](docs/six-month-quality-roadmap.md)
- [InferEdgeEnv Portfolio Summary](docs/portfolio_summary.md)
- [Evidence Contract Conformance Suite](docs/evidence-contract-conformance-suite.md)
- [CLI Error Message Polish](docs/cli-error-message-polish.md)
- [Local Real Benchmark Example Guide](docs/local-real-benchmark-example.md)
- [Local Runner Design](docs/local-runner-design.md)
- [Resource Metrics Design](docs/resource-metrics-design.md)
- [Sampler Metadata Artifact Policy](docs/sampler-metadata-artifact-policy.md)
- [Bundle Report Generation Design](docs/bundle-report-generation-design.md)

## Benchmark Config Example

```yaml
name: yolov8n-fire-fake
command: python run_yolov8n.py --input fire.jpg
model_name: yolov8n-fire
model_version: "1.0"
model_format: onnx
model_path: models/yolov8n-fire.onnx
task: object-detection
input_shape: [1, 3, 640, 640]
input_dtype: float32
runtime: fake-runtime
execution_provider: fake-provider
precision: fp32
batch_size: 1
warmup_runs: 3
repeat_runs: 10
include_preprocess: true
include_postprocess: true
timeout_seconds: 30
working_directory: .
extra_env:
  LOCAL_DEMO_FLAG: enabled
```

## Target Profile Example

```yaml
target_name: local-fake
target_type: fake
board_name: local-dev-machine
os: macOS
runtime_tags:
  - fake
  - local
```

MVP v1 accepts `fake` and `local` target types. SSH is reserved for a later version.

## Comparability Rules

Required same-condition fields:

- `model_hash`
- `input_shape`
- `input_dtype`
- `task`
- `precision`
- `batch_size`
- `warmup_runs`
- `repeat_runs`
- `include_preprocess`
- `include_postprocess`

If these fields match and runtime, execution provider, and target also match, EdgeEnv reports:

```text
Comparable: Yes
Mode: same-condition
```

For same-condition comparisons only, `report compare` also prints supplemental latency and throughput deltas after the comparability judgement. Conditional and non-comparable reports do not print metric deltas, and EdgeEnv does not produce rankings or composite scores.

Generate a comparability-first runtime regression report when you need
machine-readable evidence for a baseline/candidate pair:

```bash
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

`runtime_operation_summary` and `runtime_telemetry` remain supplemental run
evidence. They are preserved in `result.json` and returned by `runs show`, but
they are not required same-condition comparability fields. Runtime telemetry is
also written as `runtime_telemetry.json` when present so a run bundle can carry
history/replay seed evidence without promoting telemetry into a production
monitoring store.

Use `edgeenv runs telemetry export-history --output <path>` to aggregate
registered run telemetry into an `edgeenv.runtime-telemetry-history.v1` JSON
artifact. The export records missing telemetry as an evidence gap and remains
local replay evidence, not production monitoring.
If an InferEdgeOrchestrator sustained run produced an
`edgeenv_runtime_telemetry_feed` artifact, attach it during export:

```bash
edgeenv runs telemetry export-history \
  --orchestrator-feed /tmp/orchestrator-edgeenv-feed.json \
  --output /tmp/edgeenv-runtime-telemetry-history.json
```

The feed is stored as supplemental operation context for the matching run ID.
It does not replace Runtime telemetry, change comparability, or act as a
regression judgement. EdgeEnv also validates the Orchestrator producer markers
`source_repository=InferEdgeOrchestrator`,
`artifact_role=orchestrator-supplemental-operation-context`, and
`producer_contract=inferedge-orchestrator-edgeenv-runtime-telemetry-feed-v1`
before preserving the feed in telemetry history.
When the upstream Orchestrator evidence originated from the remote dispatch
starter path, EdgeEnv treats it the same way: as preserved operation context and
handoff traceability only. EdgeEnv does not confirm production remote
execution, long-lived worker readiness, secure tunnel operation, production
retry/failover, or cloud orchestration. It preserves the boundary markers so
AIGuard can emit optional deterministic diagnosis evidence and Lab can keep the
final deployment decision. Those preserved markers include
`evidence_role=remote_dispatch_runtime_event_compact_summary`,
`operation_boundary=remote dispatch starter evidence only`, and
`production_remote_execution=false` when Orchestrator provides them.
When device-local producer lineage is present, EdgeEnv also requires the feed's
`downstream_guard_alignment.producer_lineage_evidence_type` to remain
`edgeenv_orchestrator_producer_lineage`, and keeps that marker separate from
queue/thermal operation evidence candidates.
If the feed carries an entrypoint-derived `operation_risk_summary`, EdgeEnv
preserves it as read-only navigation context after checking the ownership
markers `evidence_role=derived_navigation_context`, `decision_owner=lab`,
`scheduler_owner=orchestrator`, and `not_a_deployment_decision=true`. Queue
pressure, max-pressure task, worker-health, and device-local event count markers
remain supplemental Orchestrator context; they do not become regression
judgements or comparability gates.
If the feed carries Orchestrator `operation_risk_rollup` or
`operation_timeline_summary` inside `candidate_context.operation`, EdgeEnv also
preserves and validates those compact supplemental markers for AIGuard/Lab
handoff. The rollup must keep
`schema_version=inferedge-orchestrator-operation-risk-rollup-v1`,
`operation_context_role=supplemental`, `decision_owner=lab`,
`scheduler_owner=orchestrator`, and `not_a_deployment_decision=true`. The
timeline must keep
`schema_version=inferedge-orchestrator-operation-timeline-summary-v1`. These
blocks remain operation review context only; EdgeEnv does not turn them into
comparability gates or deployment decisions.
If that preserved operation context includes Orchestrator
`stale_drop_summary` or an operation timeline `stale_drop` block, EdgeEnv
validates the compact stale-drop boundary markers
`schema_version=inferedge-orchestrator-stale-drop-summary-v1`,
`operation_context_role=supplemental`, `scheduler_owner=orchestrator`,
`decision_owner=lab`, and `not_a_deployment_decision=true`. The inspect and
handoff summaries expose matching run IDs as stale-drop traceability metadata;
this remains optional operation evidence, not an EdgeEnv regression gate.
If the preserved operation context carries Orchestrator `policy_pressure_summary`
or an operation timeline `policy_pressure` block, EdgeEnv validates the same
Lab-owned boundary markers and exposes matching run IDs as
`policy_pressure_summary_run_ids` / `orchestrator_policy_pressure_summary_run_ids`.
The inspect and handoff summaries also expose aggregate policy-pressure reason
counts so reviewers can see scheduler reason distribution before opening the
raw operation timeline.
If the operation timeline also carries `worker_health_trend`, EdgeEnv validates
`schema_version=inferedge-orchestrator-worker-health-trend-v1`,
`operation_context_role=supplemental`, `scheduler_owner=orchestrator`,
`decision_owner=lab`, and `not_a_deployment_decision=true`, then reports
matching runs as `worker_health_trend_run_ids` in inspect output and
`orchestrator_worker_health_trend_run_ids` in the Lab handoff summary. Worker
health trend is preserved as scheduler-owned operation context for Lab/AIGuard
review; it is not a comparability field, regression threshold, or deployment
decision.
If the operation timeline carries `pressure_window`, EdgeEnv validates
`schema_version=inferedge-orchestrator-pressure-window-summary-v1`,
`operation_context_role=supplemental`, `scheduler_owner=orchestrator`,
`decision_owner=lab`, and `not_a_deployment_decision=true`, then reports
matching runs as `pressure_window_summary_run_ids` in inspect output and
`orchestrator_pressure_window_summary_run_ids` in the Lab handoff summary. The
pressure-window block is preserved as reviewer navigation for sustained
overload intervals; it does not become an EdgeEnv regression gate or a
deployment decision.
Use `edgeenv runs telemetry inspect-history <path>` to validate and summarize
that replay artifact before attaching it to a regression report. Add
`--require-device-local-producer` when the handoff must prove that preserved
Orchestrator context still carries device-local `candidate_context.producer`
lineage and its producer-lineage guard alignment marker through EdgeEnv
history/replay. This gate validates lineage only; it does not change
comparability, compute regression, or make Orchestrator the deployment decision
owner. The intended local flow is export history, inspect the replay artifact,
then pass it to `report regression --telemetry-history`.
If Runtime includes `runtime_telemetry.coverage`, EdgeEnv preserves it in the
history artifact and inspect summary as evidence quality metadata. Missing
coverage fields are visible as coverage gaps, but they do not fail the run or
change comparability.
If Runtime includes `runtime_telemetry.history_seed`, EdgeEnv preserves it as
`runtime_telemetry_history_seed`, validates the EdgeEnv/Lab ownership markers,
and counts it as `summary.history_seed_runs` for local replay/history
accumulation. If the seed includes `run_config`, EdgeEnv validates and counts
that replay/comparability context separately as
`summary.history_seed_run_config_runs`. This remains local-first artifact
evidence, not production monitoring.

`report regression` reuses the same comparability gate. It only computes
mean/p95/p99/FPS/resource deltas for `Comparable: Yes` with
`Mode: same-condition`. Runtime/provider or target differences are reported as
`runtime-comparison` or `target-comparison`; protocol mismatches are reported
as `protocol_mismatch` with a rerun recommendation. The default starter policy
marks mean latency +15%, p99 +25%, FPS -20%, and memory peak +30% as review or
warning evidence. This is local regression evidence, not cloud monitoring,
ranking, or production observability.

When `--telemetry-history` is provided, `report regression` attaches runtime
telemetry coverage and evidence-gap context to the JSON/Markdown report. This
context is supplemental; it does not make non-comparable runs eligible for
regression delta calculation.

After generating a regression report, write an EdgeEnv producer-side handoff
manifest for Lab's Runtime Intelligence bundle:

```bash
edgeenv report runtime-intelligence-handoff \
  --baseline-result .edgeenv/runs/<baseline_run_id>/result.json \
  --candidate-result .edgeenv/runs/<candidate_run_id>/result.json \
  --edgeenv-regression-report /tmp/edgeenv-regression.json \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output /tmp/edgeenv-runtime-intelligence-lab-handoff.json
```

The handoff manifest records source repository mapping, artifact roles, and
producer contract markers for the Runtime result, EdgeEnv regression report,
optional Orchestrator feed context, and Lab-owned deployment report boundary.
When a Lab-compatible legacy Runtime result fixture does not carry a top-level
`run_id`, EdgeEnv anchors the handoff identity to the EdgeEnv regression
report's `baseline_run_id` / `candidate_run_id`; if a result does declare
`run_id`, it must still match the regression report.
When Runtime history seeds are present, the handoff step validates the preserved
`runtime_telemetry_history_seed` schema, `registry_owner=edgeenv`,
`decision_owner=lab`, replay point evidence, and any seed `run_config` field
types before writing the manifest. The manifest also summarizes compact
`history_seed_run_config_markers` such as shape, input mode/preprocess, power
mode, Jetson clocks, warmup, and repeat runs so Lab can show replay
traceability without reinterpreting the full Runtime result.
When preserved Orchestrator context is present, the handoff step also validates
device-local `candidate_context.producer` lineage, including per-task source
mapping, per-task stage mapping, and positive producer/device-local event
counts. It also validates the downstream
`edgeenv_orchestrator_producer_lineage` marker so Lab/AIGuard can distinguish
producer-lineage evidence from queue/thermal operation evidence. It reports
`producer_lineage_guard_alignment_run_ids` and prints the matching run IDs as
EdgeEnv producer-side traceability evidence.
If the preserved Orchestrator context includes `runtime_task_event_summary`,
the manifest also records `orchestrator_task_event_rollup_run_ids` so Lab can
gate the downstream `edgeenv_orchestrator_task_event_rollup` evidence row
without making EdgeEnv or AIGuard the deployment decision owner.
It also exposes a `lab_bundle_alignment` block so Lab can align file keys,
source repositories, artifact roles, and producer contracts while treating
AIGuard `guard_analysis` as an external artifact produced by InferEdgeAIGuard.
That alignment block also lists the external AIGuard evidence types expected by
Lab's Runtime Intelligence gate, including
`runtime_history_seed_run_config_traceability`, `edgeenv_orchestrator_producer_lineage`,
`edgeenv_orchestrator_operation_risk_rollup`,
`edgeenv_orchestrator_task_event_rollup`,
`edgeenv_orchestrator_operation_timeline_summary`,
`edgeenv_orchestrator_scheduler_fairness_summary`,
`edgeenv_orchestrator_policy_pressure_summary`,
`runtime_queue_overload`, `runtime_thermal_instability`, and
`remote_execution_recovered_by_fallback` when the downstream bundle uses that
path. EdgeEnv can declare the handoff contract without producing the Guard
artifact itself. The same block
records that the declaration is validated downstream by AIGuard's
`check-edgeenv-handoff-alignment` command and Lab's Runtime Intelligence bundle
manifest gate.
For reviewer navigation, this handoff also names the upstream Orchestrator
curated samples that explain the path without making them EdgeEnv benchmark
outputs or deployment inputs: `agent_scheduler_delay_sample.json` can map to
AIGuard `scheduler_delay_pattern`, and `remote_fallback_recovery_sample.json`
can map to `remote_execution_recovered_by_fallback` before Lab renders the
corresponding report markers.
The alignment block separately declares optional AIGuard evidence types
`stale_frame_risk`, `edgeenv_orchestrator_stale_drop_summary`, and
`edgeenv_orchestrator_pressure_window_summary` for newer sustained
Orchestrator context. They are optional so EdgeEnv can preserve stale-drop or
pressure-window evidence when present without rejecting older queue/thermal
feeds or changing Lab's required Runtime Intelligence bundle set.
`lab_bundle_alignment.optional_aiguard_source_traceability` mirrors the
AIGuard optional-present source artifact and regeneration command as read-only
metadata:
`InferEdgeAIGuard/examples/runtime_intelligence/aiguard_runtime_operation_guard_analysis_optional_stale_drop.json`
and `python -m inferedge_aiguard.cli build-runtime-intelligence-optional-stale-drop`.
This lets downstream reviewers connect the EdgeEnv handoff to the AIGuard
source fixture without making EdgeEnv produce `guard_analysis`.
Verify the EdgeEnv-owned replay/regression/handoff path locally with:

```bash
bash scripts/smoke_runtime_intelligence_replay_regression_handoff.sh \
  --output-dir reports/runtime_intelligence_replay_regression_handoff
```

This smoke records two local runtime-telemetry runs, exports and inspects an
`edgeenv.runtime-telemetry-history.v1` replay artifact, generates a
comparability-first regression report with `--telemetry-history`, and writes
the Runtime Intelligence Lab handoff manifest. It checks that
`history_seed_run_config` markers reach the handoff summary, that regression
deltas remain gated by `same-condition` comparability, and that EdgeEnv still
does not produce AIGuard `guard_analysis`.
Verify that producer-side source traceability path locally with:

```bash
bash scripts/smoke_runtime_intelligence_source_traceability.sh \
  --output-dir reports/runtime_intelligence_source_traceability
```

When a sibling InferEdgeLab checkout is available, this smoke also runs Lab's
source traceability gate against the generated EdgeEnv handoff manifest and the
AIGuard optional-present alignment fixture.
The same `lab_bundle_alignment.expected_report_markers` list declares the
Lab-owned report markers that downstream Lab gates must preserve:
`Runtime Intelligence Risk Summary`, `Runtime replay duration scope`,
`Orchestrator operation feed context`, `EdgeEnv fixture matrix coverage`,
`Reviewer operation quick scan`, `Orchestrator task event rollup`,
`Lab EdgeEnv preservation context`,
`AIGuard operation risk rollup evidence`,
`AIGuard task event rollup evidence`,
`AIGuard operation timeline evidence`,
`AIGuard scheduler fairness evidence`,
`AIGuard policy pressure evidence`,
`AIGuard runtime operation anomalies`, `AIGuard remote dispatch event summary`,
`AIGuard remote event summary consistency`, `Remote fallback starter evidence`,
`lab=Remote fallback starter evidence; evidence=remote_execution_recovered_by_fallback`,
`AIGuard producer-lineage guard alignment`, and
`Lab remains the final deployment decision owner.`.
When the EdgeEnv regression context carries optional replay-duration metadata,
the handoff summary also preserves `duration_source` and
`duration_scope_label` values such as `source=entrypoint_requested_frames` as
producer-side traceability metadata for the Lab row.
It does not include AIGuard `guard_analysis`; AIGuard remains a separate
deterministic diagnosis provider.

After AIGuard creates the external `guard_analysis`, verify the cross-repo
alignment with:

```bash
python -m inferedge_aiguard.cli check-edgeenv-handoff-alignment \
  --edgeenv-handoff /tmp/edgeenv-runtime-intelligence-lab-handoff.json \
  --guard-analysis /tmp/aiguard-runtime-operation-guard-analysis.json
```

If required fields differ, EdgeEnv reports:

```text
Comparable: No
Reason:
- Different model hash
- Different input shape
```

If required fields match but runtime, execution provider, or target differs, EdgeEnv reports:

```text
Comparable: Conditional
Mode: runtime-comparison
Reason:
- Same model hash
- Same input shape
- Different runtime or execution provider
```

## Local Registry Layout

```text
.edgeenv/
  runs.db
  runs/
    <run_id>/
      result.json
      config.yaml
      target.yaml
      env.json
      stdout.log
      stderr.log
      runtime_telemetry.json  # optional
  failed-runs/
    <run_id>/
      failure.json
      config.yaml
      target.yaml
      env.json
      stdout.log
      stderr.log
```

`runs.db` is a local SQLite index. The run directory remains the evidence bundle.
Failed local runs are stored under `failed-runs/` for debugging and are not inserted into `runs.db`. Use `edgeenv failed-runs list` and `edgeenv failed-runs show <run_id>` to inspect failed-run artifacts safely.

Resource metrics remain canonical in `result.json`. `runs.db` also keeps a rebuildable `resource_metric_index` so `edgeenv runs resources list --metric <name>` can find runs by normalized memory, power, energy, or temperature evidence without turning those values into rankings or comparability gates. Add `--json` when scripts need the same supplemental lookup results with explicit filters, units, and source counts.

Use `edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip` to create a portable successful-run evidence bundle. Use `edgeenv runs import edgeenv-run-<run_id>.zip` to validate the bundle, copy it into `.edgeenv/runs/`, and rebuild the local registry row. Optional `runtime_telemetry.json` is exported/imported with manifest checksum validation when present.

Use `edgeenv failed-runs export <run_id> --output edgeenv-failed-run-<run_id>.zip` and `edgeenv failed-runs import edgeenv-failed-run-<run_id>.zip` for portable failed-run diagnostic evidence. Failed-run import copies files into `.edgeenv/failed-runs/` and does not update `runs.db`. The artifact-first zip contract is described in [Export/Import Design](docs/export-import-design.md).

Use `edgeenv report bundle-summary --scenario <label>:<run_id_a>:<run_id_b>` to generate a read-only Markdown handoff summary from imported successful runs and normal compare judgement. The summary is for human review only; it does not replace `result.json`, sampler artifacts, manifests, or `report compare`.

## Relation To InferEdge And EdgeBench

InferEdge validates whether a model is deployable across build provenance, runtime execution, evaluation, comparison, optional diagnosis, and deployment decision reports.

In portfolio terms, InferEdgeLab is the validation / decision layer. InferEdgeEnv is the v0.1.5 v1-complete experiment hygiene / comparability layer.

InferEdgeEnv records whether benchmark evidence can be trusted and compared. Its scope is narrower and separate: local run artifacts, SQLite registry rows, portable evidence bundles, and comparability judgement.

In the top-level InferEdge ecosystem map, InferEdgeEnv is the v0.1.5 v1-complete experiment hygiene / comparability layer. It is not part of the pinned Core 4 validation path, but it has a completed role: preserving benchmark evidence and judging same-condition, conditional, or non-comparable runs before any metric delta is discussed.

InferEdgeOrchestrator is also separate: it is the post-deployment operation-control layer for scheduling, load shedding, telemetry, and runtime coordination after a model is already deployed. InferEdgeEnv does not control live inference operations; it records benchmark evidence and preserves honest comparison boundaries before or around review handoff.

Remote dispatch starter evidence follows the same boundary. Orchestrator
produces worker-selection, fallback, and compact event-summary evidence;
EdgeEnv may preserve related operation context and handoff markers as local
evidence; AIGuard may explain deterministic warning context; Lab owns the final
deployment decision. EdgeEnv is not a remote execution system or operation
control plane. In this path, EdgeEnv preserves remote dispatch markers only as
registry/replay traceability, including the compact summary role, starter-only
operation boundary, and `production_remote_execution=false` flag.

EdgeBench is adjacent in benchmark motivation, but InferEdgeEnv is not a public leaderboard. It is a local-first run evidence registry and comparability checker, not a ranking surface.

## MVP Scope

Included in MVP v1:

- Python CLI skeleton
- Typer-based CLI
- Rich output
- Pydantic benchmark config and target profile schemas
- FakeRunner deterministic benchmark result
- LocalRunner command execution with explicit metrics JSON capture
- Local runtime adapter example for user-owned command integration
- Result JSON and artifact directory creation
- SQLite local registry
- `runs list` and `runs show`
- `runs resources list`
- `runs export`
- `runs import`
- `failed-runs list`, `failed-runs show`, `failed-runs export`, and `failed-runs import`
- Jetson `tegrastats` wrapper example for optional resource metrics
- `report compare` comparability checker
- `report bundle-summary` read-only Markdown handoff summary
- pytest tests

Non-goals:

- OS, VM, WSL, Docker, SSH target implementation
- Cloud DB, auth, web dashboard, public leaderboard
- Model or dataset upload service
- Single-score model ranking

## Design Notes

- [MVP Readiness Checklist](docs/mvp-readiness-checklist.md)
- [EdgeEnv MVP v1 Handoff Status](docs/v1-handoff-status.md)
- [EdgeEnv MVP v1 Release Rehearsal](docs/v1-release-rehearsal.md)
- [Packaging And Entrypoint Readiness](docs/packaging-entrypoints.md)
- [CI Readiness Workflow](docs/ci-readiness.md)
- [Local Runner Design](docs/local-runner-design.md)
- [Local Command Contract Guide](docs/local-command-contract.md)
- [Compare Workflow Guide](docs/compare-workflow-guide.md)
- [Failed Run Inspection Guide](docs/failed-run-inspection.md)
- [Resource Metrics Design](docs/resource-metrics-design.md)
- [Runtime Operation Summary Evidence](docs/runtime-operation-summary-evidence.md)
- [Sampler Failure Policy](docs/sampler-failure-policy.md)
