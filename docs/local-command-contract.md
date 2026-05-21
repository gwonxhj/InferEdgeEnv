# Local Command Contract Guide

> Language: English | [한국어/원문](language.md#korean-overview)

## 1. WHAT — What This Document Defines

This guide defines the stdout contract, benchmark config expectations, and failure triage path for connecting a user-owned benchmark command to the `target_type: local` runner.

EdgeEnv does not run the model for you and does not infer benchmark metrics from arbitrary logs. The local command owns the benchmark loop and must emit explicit JSON lines on stdout so EdgeEnv can validate and preserve the evidence.

## 2. CONTENTS — Files And Stack

Related files:

- `inferedge_env/runners/local.py` — local command execution and stdout contract parser
- `examples/scripts/adapter_template.py` — copyable adapter for wrapping a user-owned runtime command
- `examples/benches/local_adapter_template.yaml` — benchmark config for the adapter template
- `examples/scripts/local_benchmark_template.py` — minimal benchmark loop template
- `examples/benches/local_template.yaml` — benchmark config for the minimal template
- `examples/scripts/local_runtime_adapter_demo.py` — richer runtime command adapter example
- `examples/benches/local_runtime_adapter.yaml` — benchmark config for the runtime adapter demo
- `examples/profiles/local.yaml` — local target profile
- `docs/local-real-benchmark-example.md` — walkthrough for wiring a real runtime command
- `docs/local-runner-design.md` — internal local runner design
- `docs/resource-metrics-design.md` — optional resource metrics contract
- `docs/sampler-failure-policy.md` — sampler/resource metrics failure policy

Stack: Python, YAML, stdout JSON line contract

## 3. HOW — Connect A Command

### Minimal Command Shape

A benchmark command may print normal logs, but it must emit an `EDGEENV_METRICS_JSON=` line on stdout:

```text
EDGEENV_METRICS_JSON={"latency_mean_ms":12.3,"latency_p50_ms":12.0,"latency_p95_ms":14.1,"latency_p99_ms":15.0,"throughput_fps":81.3}
```

Required primary metrics:

- `latency_mean_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `throughput_fps`

Optional resource metrics:

```text
EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":512.0,"power_mean_w":8.2,"source":"my-tool"}
```

If the command cannot produce reliable resource metrics, omit the resource metrics line. The benchmark run can still succeed; EdgeEnv will preserve the primary result and simply omit the `resource_metrics` field.

Optional runtime operation summary:

```text
EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON={"source":"inferedge-runtime","health_reason":"completed"}
```

If the command cannot produce structured runtime operation context, omit this
line. When present, it must be a JSON object. EdgeEnv preserves it as
supplemental run evidence in `result.json` and `runs show`; it does not become a
same-condition comparability gate.

### Template Flow

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv runs show <run_id>
```

`examples/scripts/local_benchmark_template.py` shows:

- how to read EdgeEnv-injected `EDGEENV_*` environment variables
- how to read command-specific `extra_env`
- where to place the actual measurement loop
- how to emit the primary metrics JSON line
- how to emit optional resource metrics when they are available

### Runtime Adapter Flow

Start with the copyable adapter template when you already have a benchmark command to wrap:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_adapter_template.yaml
edgeenv runs show <run_id>
```

`examples/scripts/adapter_template.py` runs the command after `--`, forwards diagnostic stdout/stderr, exits with the wrapped command code on failure, and only emits `EDGEENV_METRICS_JSON=` after the wrapped command succeeds. Copy this file when wiring a real user-owned runtime command.

The deterministic demo keeps the wrapped command intentionally small:

```text
python examples/scripts/adapter_template.py [adapter args] -- python -c "print('adapter-template-runtime')"
```

Use the richer demo when you want a more opinionated example with protocol arguments:

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_runtime_adapter.yaml
edgeenv runs show <run_id>
```

`examples/scripts/local_runtime_adapter_demo.py` shows the next step after the minimal template: wrap a user-owned runtime command, pass through diagnostic stdout/stderr, fail if that command fails, and emit EdgeEnv metrics/resource metrics lines. See [Local Real Benchmark Example Guide](local-real-benchmark-example.md) for the full walkthrough.

### Benchmark Config Checklist

- `command` must be executable on the current machine.
- Paths that need quoting should be quoted in the config command.
- If `working_directory` is set, the command runs from that directory.
- `timeout_seconds` is the timeout for the whole command.
- `extra_env` keys must be uppercase and must not use the `EDGEENV_` prefix.
- `warmup_runs` and `repeat_runs` do not make EdgeEnv repeat the subprocess. The benchmark command must implement the measurement loop that follows that protocol.

### Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `Missing EDGEENV_METRICS_JSON=<json> line in stdout` | The command did not emit primary metrics | Print an `EDGEENV_METRICS_JSON=` line on stdout |
| `Invalid EDGEENV_METRICS_JSON JSON` | JSON quoting, comma, or braces are invalid | Use a structured JSON writer such as `json.dumps(...)` |
| `Invalid local metrics schema` | Required latency/throughput fields are missing or typed incorrectly | Emit all five required primary metrics as numeric values |
| `Invalid EDGEENV_RESOURCE_METRICS_JSON JSON` | Optional resource metrics JSON is malformed | Omit the line when valid resource metrics are unavailable |
| `Invalid local resource metrics schema` | Unknown fields or invalid types were emitted | Use only supported unit-suffixed `ResourceMetrics` fields |
| `Invalid EDGEENV_RUNTIME_OPERATION_SUMMARY_JSON JSON` | Optional operation summary JSON is malformed | Omit the line when structured operation evidence is unavailable |
| `Invalid local runtime operation summary schema` | Operation summary is not a JSON object | Emit an object, not an array/string/number |
| `Local benchmark command failed with exit code N` | The benchmark command itself failed | Use `edgeenv failed-runs list` and `edgeenv failed-runs show <run_id>` to inspect stdout/stderr |
| `Local benchmark command timed out after ... seconds` | The command did not finish within `timeout_seconds` | Shorten the benchmark loop or increase the timeout |
| `Failed to start local benchmark command` | The command path is missing or not executable | Check `command`, `working_directory`, virtualenv, and PATH setup |

CLI failures print the original `Error:` plus a short `Hint:`. For local benchmark failures, EdgeEnv also writes `.edgeenv/failed-runs/<run_id>/` and prints an `edgeenv failed-runs show <run_id> --edgeenv-root <root>` command so stdout/stderr can be inspected without treating the failed command as a successful run.

## 4. HOW NOT — What To Avoid

- Do not assume a human-readable latency log is enough.
- Do not print `EDGEENV_METRICS_JSON=` to stderr. The local runner reads the stdout contract.
- Do not hand-concatenate JSON strings when a structured JSON writer is available.
- Do not emit placeholder strings or unit-suffixed strings when resource metrics are unknown.
- Do not hide benchmark failures by printing success metrics anyway.
- Do not treat runtime operation context as a replacement for protocol-first comparability.
- Do not present Docker, WSL, SSH, or cloud execution as the default local command path.

## 5. WHERE — Related Design Boundaries

- **Local Runner Design**: this guide turns the local runner design into a user-facing contract.
- **Resource Metrics Design**: optional resource metrics fields and storage policy.
- **Runtime Operation Summary Evidence**: optional runtime operation context preservation policy.
- **Sampler Failure Policy**: omit uncertain sampler/resource evidence; validate it if emitted.
- **Registry Resource Query Design**: `result.json` is the source of truth for resource metrics, while `runs resources list` is a rebuildable lookup surface.

## 6. WHY — Background Judgment

EdgeEnv's comparability value comes from an explicit evidence contract, not from clever benchmark log parsing. The user controls the runtime, model, input, and measurement loop inside the command; EdgeEnv validates and freezes the resulting evidence as local artifacts.

This guide reduces the ambiguity that usually appears when a sample works but a real user-owned command does not.

## 7. LEARNED CAUTIONS — Learned Cautions

_(None yet)_
