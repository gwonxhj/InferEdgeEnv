# EdgeEnv

EdgeEnv is a config-driven Edge AI inference benchmark runner, local result registry, and comparability checker.

## Problem

Edge inference results are easy to record but hard to compare honestly. A latency number is only meaningful when model identity, input shape, precision, batch size, warmup/repeat protocol, and preprocess/postprocess boundaries are known.

EdgeEnv focuses on recording benchmark evidence locally and judging whether two runs are directly comparable, conditionally comparable, or not comparable.

## What EdgeEnv Is Not

EdgeEnv is not:

- An OS, bootloader, GRUB, BCD, or Linux compatibility layer
- A VM, Docker, WSL, or cloud target manager
- A cloud database, login/auth system, web dashboard, or public leaderboard
- A model upload server or dataset upload server
- A single-score ranking system for all models

## Quickstart

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

### 2. Record a Local Command Run

Then try the local runner examples. These execute small deterministic Python commands on the current machine.

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_echo_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
```

The local target executes `command` on the current machine and reads an explicit `EDGEENV_METRICS_JSON=` line from stdout. Local commands may also emit an optional `EDGEENV_RESOURCE_METRICS_JSON=` line for memory, power, energy, or temperature evidence. `bench run` reports whether resource metrics were stored or omitted.

To connect your own benchmark command, start from `examples/scripts/local_benchmark_template.py`, then review the adapter pattern in [Local Real Benchmark Example Guide](docs/local-real-benchmark-example.md).

### 3. Try Sampler Wrapper Cases

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

### 4. Inspect Evidence

`runs show` reads the result artifact and includes resource evidence when the local command emits it:

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
  }
}
```

### 5. Compare Runs

Compare two registered runs after you have at least two successful run IDs:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_a.yaml
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_compare_b.yaml
edgeenv runs list
edgeenv report compare <run_id_a> <run_id_b>
```

For the full flow, see [Compare Workflow Guide](docs/compare-workflow-guide.md).

The fake target uses `FakeRunner`, so it does not execute a real model.
Local benchmark configs may set `timeout_seconds`, `working_directory`, and uppercase `extra_env` keys for controlled command execution.
The Python package is `inferedge_env`; the user-facing CLI command remains `edgeenv`.

## Guide Map

Start here:

- [MVP Readiness Checklist](docs/mvp-readiness-checklist.md) — what works in this MVP and what remains out of scope
- [EdgeEnv MVP v1 Handoff Status](docs/v1-handoff-status.md) — current state, validation commands, and next work candidates
- [EdgeEnv MVP v1 Release Rehearsal](docs/v1-release-rehearsal.md) — main-based user-flow rehearsal and v1 tag gate
- [Packaging And Entrypoint Readiness](docs/packaging-entrypoints.md) — install, module entrypoint, and console script checks
- [CI Readiness Workflow](docs/ci-readiness.md) — automated PR/main checks for MVP contracts
- [Local Command Contract Guide](docs/local-command-contract.md) — how to connect your own local benchmark command
- [Local Real Benchmark Example Guide](docs/local-real-benchmark-example.md) — how to wrap a user-owned runtime command
- [Jetson Tegrastats Wrapper Guide](docs/jetson-tegrastats-wrapper.md) — how to collect Jetson `tegrastats` as optional resource evidence
- [Jetson Sampled Run Rehearsal](docs/jetson-sampled-run-rehearsal.md) — real Jetson sampler adapter run, inspection UX, and export/import validation
- [Jetson Environment Setup Hardening](docs/jetson-env-setup-hardening.md) — source snapshot + conda/PYTHONPATH smoke for repeated Jetson validation
- [Jetson Sampled Comparison Rehearsal](docs/jetson-sampled-comparison-rehearsal.md) — two sampled Jetson runs proving compare remains protocol-first
- [Jetson Sampled Conditional Comparison Rehearsal](docs/jetson-sampled-conditional-comparison-rehearsal.md) — sampled Jetson provider difference proving Conditional compare suppresses metric deltas
- [Jetson Sampled Target Comparison Rehearsal](docs/jetson-sampled-target-comparison-rehearsal.md) — sampled Jetson target difference proving target-comparison suppresses metric deltas
- [Jetson Sampled Evidence Bundle Handoff](docs/jetson-sampled-evidence-bundle-handoff.md) — export/import sampled bundles proving imported compare keeps the same interpretation rules
- [Jetson Sampled Bundle Portability Review](docs/jetson-sampled-bundle-portability-review.md) — short human-readable handoff report format for sampled evidence bundles
- [Bundle Report Generation Design](docs/bundle-report-generation-design.md) — read-only Markdown summary generation from imported artifacts and compare output
- [Sampler Adapter API Design](docs/sampler-adapter-api-design.md) — future sampler adapter lifecycle and metadata schema
- [LocalRunner Sampler Wiring Design](docs/local-runner-sampler-wiring-design.md) — how LocalRunner should enable sampler lifecycle without breaking stdout metrics
- [Sampler Metadata Artifact Policy](docs/sampler-metadata-artifact-policy.md) — where sampler metadata/raw artifacts belong
- [Compare Workflow Guide](docs/compare-workflow-guide.md) — how to create two runs and judge comparability
- [Export/Import Design](docs/export-import-design.md) — proposed portable evidence bundle contract

Design references:

- [Local Runner Design](docs/local-runner-design.md)
- [Resource Metrics Design](docs/resource-metrics-design.md)
- [Sampler Failure Policy](docs/sampler-failure-policy.md)
- [Platform Sampler Design](docs/platform-sampler-design.md)
- [Sampler Adapter API Design](docs/sampler-adapter-api-design.md)
- [LocalRunner Sampler Wiring Design](docs/local-runner-sampler-wiring-design.md)
- [Sampler Metadata Artifact Policy](docs/sampler-metadata-artifact-policy.md)
- [Registry Resource Query Design](docs/registry-resource-query-design.md)

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

Use `edgeenv runs export <run_id> --output edgeenv-run-<run_id>.zip` to create a portable successful-run evidence bundle. Use `edgeenv runs import edgeenv-run-<run_id>.zip` to validate the bundle, copy it into `.edgeenv/runs/`, and rebuild the local registry row.

Use `edgeenv failed-runs export <run_id> --output edgeenv-failed-run-<run_id>.zip` and `edgeenv failed-runs import edgeenv-failed-run-<run_id>.zip` for portable failed-run diagnostic evidence. Failed-run import copies files into `.edgeenv/failed-runs/` and does not update `runs.db`. The artifact-first zip contract is described in [Export/Import Design](docs/export-import-design.md).

Use `edgeenv report bundle-summary --scenario <label>:<run_id_a>:<run_id_b>` to generate a read-only Markdown handoff summary from imported successful runs and normal compare judgement. The summary is for human review only; it does not replace `result.json`, sampler artifacts, manifests, or `report compare`.

## Relation To InferEdge And EdgeBench

InferEdge is a broader validation evidence workflow around build provenance, runtime execution, evaluation, comparison, optional diagnosis, and deployment decision reports.

EdgeEnv keeps a narrower scope: local benchmark execution metadata, result storage, and comparability judgement. It shares InferEdge's evidence-first philosophy but does not try to become the full InferEdge validation pipeline.

EdgeBench is adjacent in benchmark motivation, but EdgeEnv is not a public leaderboard. It is a local-first tool for reproducible result recording and comparability checks.

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
- [Sampler Failure Policy](docs/sampler-failure-policy.md)
