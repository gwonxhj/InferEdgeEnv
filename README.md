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
edgeenv profile validate examples/profiles/local_fake.yaml
edgeenv bench validate examples/benches/yolov8n_fire.yaml
edgeenv bench run --target examples/profiles/local_fake.yaml --config examples/benches/yolov8n_fire.yaml
edgeenv runs list
edgeenv runs show <run_id>
edgeenv report compare <run_id_a> <run_id_b>
```

Local resource metrics example:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_resource_metrics.yaml
edgeenv runs show <run_id>
```

`runs show` includes the resource evidence from `result.json` when the local command emits it:

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

The fake target uses `FakeRunner`, so it does not execute a real model.
The local target executes `command` on the current machine and reads an explicit `EDGEENV_METRICS_JSON=` line from stdout.
Local commands may also emit an optional `EDGEENV_RESOURCE_METRICS_JSON=` line for memory, power, energy, or temperature evidence.
Local benchmark configs may set `timeout_seconds`, `working_directory`, and uppercase `extra_env` keys for controlled command execution.
`edgeenv runs show <run_id>` reads the result artifact and includes resource metrics when present.
The Python package is `inferedge_env`; the user-facing CLI command remains `edgeenv`.

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
Failed local runs are stored under `failed-runs/` for debugging and are not inserted into `runs.db`.

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
- Result JSON and artifact directory creation
- SQLite local registry
- `runs list` and `runs show`
- `report compare` comparability checker
- pytest tests

Non-goals:

- OS, VM, WSL, Docker, SSH target implementation
- Cloud DB, auth, web dashboard, public leaderboard
- Model or dataset upload service
- Single-score model ranking

## Design Notes

- [Local Runner Design](docs/local-runner-design.md)
- [Resource Metrics Design](docs/resource-metrics-design.md)
