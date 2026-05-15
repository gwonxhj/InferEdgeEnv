# Jetson Sampled Comparison Rehearsal

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 `sampler: jetson-tegrastats`가 켜진 sampled local run 두 개를 생성하고, `report compare`가 sampler/resource evidence가 아니라 benchmark protocol을 먼저 보고 판단하는지 확인한다.

이 리허설의 핵심은 sampler evidence가 유용한 보조 증거이지만 comparability gate가 아니라는 점을 실제 Jetson 흐름으로 닫는 것이다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_jetson_sampled_compare.sh` — 두 sampled Jetson run과 `report compare` output contract smoke
- `scripts/smoke_jetson_source_env.sh` — 단일 sampled run source snapshot smoke
- `examples/profiles/jetson_nano_sampled_local.yaml` — optional `jetson-tegrastats` sampler profile
- `examples/benches/jetson_sampled_local.yaml` — deterministic sampled benchmark config
- `docs/compare-workflow-guide.md` — compare output 해석 기준
- `docs/jetson-env-setup-hardening.md` — Jetson source snapshot 환경 기준

기술 스택: Jetson Linux, `tegrastats`, EdgeEnv local runner, SQLite registry, `report compare`

## 3. HOW — 리허설 절차

From the repo root on Jetson:

```bash
scripts/smoke_jetson_sampled_compare.sh --python /home/${JETSON_USER}/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

What the script checks:

- runtime dependencies and `tegrastats` are available
- sampled Jetson profile/config validate
- two successful runs are stored in the same local registry root
- both runs have `result.json.resource_metrics.source=jetson-tegrastats`
- both runs have `sampler/metadata.json` and listed raw sampler artifacts
- `runs sampler show` works for both run ids
- `report compare <run_id_a> <run_id_b>` prints `Comparable: Yes` and `Mode: same-condition`
- same-condition compare prints supplemental `Metrics Delta`
- compare output does not mention `resource` or `sampler` as a judgement gate

Manual equivalent:

```bash
export PYTHONPATH="$PWD"
edgeenv_root=/tmp/InferEdgeEnv-jetson-sampled-compare/.edgeenv
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$edgeenv_root"
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$edgeenv_root"
edgeenv runs sampler show <run_id_a> --edgeenv-root "$edgeenv_root"
edgeenv runs sampler show <run_id_b> --edgeenv-root "$edgeenv_root"
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root "$edgeenv_root"
```

## 4. HOW NOT — 피해야 할 함정

- Do not treat lower sampled power, memory, or temperature as a comparability reason.
- Do not add sampler/resource fields to required compare gates.
- Do not suppress `Metrics Delta` for same-condition runs only because sampled resource metrics differ.
- Do not describe this as remote execution support; the run still happens locally on Jetson.
- Do not commit generated `.edgeenv/`, zip exports, raw `tegrastats` logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Compare Workflow Guide**: this is the Jetson sampled version of the same-condition compare workflow.
- **Jetson Sampled Conditional Comparison Rehearsal**: validates the provider-difference conditional branch.
- **Jetson Environment Setup Hardening**: reuses the source snapshot + known Python environment pattern.
- **Sampler Metadata Artifact Policy**: sampler metadata remains artifact evidence, not registry schema.
- **Registry Resource Query Design**: resource metrics stay artifact-first even when a rebuildable lookup index exists.

## 6. WHY — 배경 판단

EdgeEnv's main value is not collecting more numbers; it is preventing unsupported comparisons. Jetson `tegrastats` adds useful platform evidence, but resource metrics can vary with host state and sampling window. Keeping compare protocol-first prevents sampled power/memory evidence from becoming an accidental leaderboard or regression gate.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Jetson sampled compare should assert that compare output does not mention sampler/resource evidence as a judgement gate.

## Validation Record — jetson-device

Status: passed on `jetson-device`.

Command:

```bash
scripts/smoke_jetson_sampled_compare.sh --python /home/${JETSON_USER}/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

Observed run ids:

```text
run-20260508-014429-36574dd2
run-20260508-014432-2fcedc8b
```

Observed `report compare`:

```text
Comparable: Yes
Mode: same-condition
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
Metrics Delta:
- latency_mean_ms: 12.3 ms -> 12.3 ms (delta 0.0 ms, +0.00%)
- latency_p50_ms: 12.0 ms -> 12.0 ms (delta 0.0 ms, +0.00%)
- latency_p95_ms: 14.1 ms -> 14.1 ms (delta 0.0 ms, +0.00%)
- latency_p99_ms: 15.0 ms -> 15.0 ms (delta 0.0 ms, +0.00%)
- throughput_fps: 81.3 fps -> 81.3 fps (delta 0.0 fps, +0.00%)
```

Observed sampled evidence:

```json
{
  "run-20260508-014429-36574dd2": {
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 908.667,
      "memory_peak_mb": 910.0,
      "power_mean_w": 4.488,
      "power_peak_w": 4.556,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 43.437
    }
  },
  "run-20260508-014432-2fcedc8b": {
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 910.667,
      "memory_peak_mb": 911.0,
      "power_mean_w": 4.467,
      "power_peak_w": 4.515,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 43.375
    }
  }
}
```

Conclusion:

- Both runs had sampler metadata and raw `tegrastats` artifacts.
- Resource metrics differed between the two runs, as expected for host-scoped samples.
- `report compare` still used the benchmark protocol and identity fields first.
- Compare output did not mention resource or sampler evidence as a judgement reason.
- Same-condition metric deltas remained latency/throughput-only supplemental evidence.
