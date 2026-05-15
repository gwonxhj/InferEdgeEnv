# Jetson Tegrastats Wrapper Guide

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 `target_type: local` runner를 유지한 채 `tegrastats` resource sampling을 EdgeEnv stdout contract로 연결하는 wrapper command 흐름을 정한다.

이 기능은 SSH target 구현이 아니다. Jetson shell에 들어가거나 Jetson에서 repo를 실행할 수 있는 상태에서, benchmark command를 local command로 실행하고 wrapper가 `EDGEENV_RESOURCE_METRICS_JSON=`를 출력하는 방식이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `examples/scripts/run_with_tegrastats.py` — Jetson `tegrastats` wrapper command
- `examples/benches/jetson_tegrastats_local.yaml` — Jetson local sampler example config
- `examples/profiles/jetson_nano_local.yaml` — Jetson local target profile example
- `examples/scripts/emit_local_metrics.py` — deterministic primary metrics stand-in
- `docs/platform-sampler-design.md` — wrapper-first sampler integration boundary
- `docs/local-command-contract.md` — required stdout metrics contract
- `docs/sampler-failure-policy.md` — optional resource metrics failure policy

기술 스택: Jetson Linux, `tegrastats`, Python subprocess, EdgeEnv resource metrics JSON

## 3. HOW — Jetson에서 실행하는 방법

### 1. Confirm platform tools

On the Jetson:

```bash
hostname
uname -a
command -v tegrastats
tegrastats --help
python3 --version
```

Observed on `jetson-device` during validation:

```text
jetson-device
Linux jetson-device 5.15.148-tegra ... aarch64 GNU/Linux
/usr/bin/tegrastats
Python 3.10.12
```

### 2. Run the wrapper directly

From the repo root on Jetson:

```bash
python examples/scripts/run_with_tegrastats.py --interval-ms 500 --startup-wait-ms 600 -- python examples/scripts/emit_local_metrics.py
```

Expected stdout includes:

```text
EDGEENV_RESOURCE_METRICS_JSON={... "source": "jetson-tegrastats" ...}
EDGEENV_METRICS_JSON={...}
```

If `tegrastats` is unavailable, the wrapper preserves the primary benchmark run and omits resource metrics unless `--require-tegrastats` is set.

### 3. Run through EdgeEnv

From the repo root on Jetson:

```bash
edgeenv profile validate examples/profiles/jetson_nano_local.yaml
edgeenv bench validate examples/benches/jetson_tegrastats_local.yaml
edgeenv bench run --target examples/profiles/jetson_nano_local.yaml --config examples/benches/jetson_tegrastats_local.yaml
edgeenv runs show <run_id>
```

The resulting `result.json` should include `resource_metrics` with whichever fields `tegrastats` exposes:

- `memory_mean_mb`
- `memory_peak_mb`
- `power_mean_w`
- `power_peak_w`
- `temperature_peak_c`
- `source: jetson-tegrastats`

### 4. Validation record

Validated on `jetson-device` with `yolo_env`:

```bash
python -m pip install -e .
python -m inferedge_env.cli doctor
edgeenv bench run --target examples/profiles/jetson_nano_local.yaml --config examples/benches/jetson_tegrastats_local.yaml --edgeenv-root /tmp/InferEdgeEnv-jetson-smoke/.edgeenv-jetson
edgeenv runs show <run_id> --edgeenv-root /tmp/InferEdgeEnv-jetson-smoke/.edgeenv-jetson
```

Observed:

```text
Benchmark run stored
Latency mean: 12.3 ms
Resource metrics: stored (source=jetson-tegrastats, fields=memory_mean_mb, memory_peak_mb, power_mean_w, power_peak_w, temperature_peak_c)
```

Observed `resource_metrics`:

```json
{
  "memory_mean_mb": 881.0,
  "memory_peak_mb": 881.0,
  "power_mean_w": 4.482,
  "power_peak_w": 4.482,
  "source": "jetson-tegrastats",
  "temperature_peak_c": 38.343
}
```

### 5. Replace the stand-in benchmark

Keep the left side of the command and replace only the command after `--`:

```text
python examples/scripts/run_with_tegrastats.py --interval-ms 500 --startup-wait-ms 600 -- <your benchmark command>
```

The wrapped benchmark command must still emit `EDGEENV_METRICS_JSON=<json>` on stdout. The wrapper ignores any wrapped command resource metrics line and uses `tegrastats` as the resource source for this path.

## 4. HOW NOT — 피해야 할 함정

- Do not treat this as SSH target execution. Run it on Jetson as a local target.
- Do not add `tegrastats` lifecycle management to `LocalRunner`.
- Do not fail a good primary benchmark only because optional `tegrastats` is unavailable, unless `--require-tegrastats` was explicitly requested.
- Do not compare resource metrics as a same-condition gate.
- Do not report `tegrastats` host-wide power as model-only energy.
- Do not commit model, dataset, engine, or trace artifacts into the repo.

## 5. WHERE — 다른 설계와의 관계

- **Platform Sampler Design**: this is the first real platform wrapper path before adding adapter APIs.
- **Resource Metrics Design**: parsed values remain optional `resource_metrics` evidence in `result.json`.
- **Local Runner Design**: `LocalRunner` still only executes command and parses explicit JSON lines.
- **Registry Resource Query Design**: resource metrics stay canonical in artifacts and can be found through a rebuildable lookup index.
- **Comparability**: resource metrics do not affect `Comparable` mode.

## 6. WHY — 배경 판단

Jetson `tegrastats` is valuable evidence, but it is platform-specific and host-scoped. Keeping it in a wrapper preserves EdgeEnv's local-first contract and avoids turning the runner into a platform manager before the integration pattern is proven.

This gives users a real Jetson path now while leaving future adapter APIs deliberate: once the wrapper semantics are stable, `inferedge_env/samplers/` can be designed around proven fields and failure behavior.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Short benchmark commands can finish before the first `tegrastats` line appears; keep `--startup-wait-ms` at least as large as one sampling interval for smoke runs.
