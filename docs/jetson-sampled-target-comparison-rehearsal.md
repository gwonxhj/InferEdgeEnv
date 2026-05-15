# Jetson Sampled Target Comparison Rehearsal

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 `sampler: jetson-tegrastats`가 켜진 sampled local run 두 개를 생성하되, 두 번째 run의 target profile metadata만 의도적으로 다르게 만들어 `report compare`가 `Mode: target-comparison`을 출력하고 metric delta를 숨기는지 확인한다.

이 리허설은 runtime/provider가 같고 target identity만 다를 때도 sampler/resource evidence가 compare gate가 아니라는 점을 실제 Jetson evidence로 검증한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_jetson_sampled_target_compare.sh` — two sampled Jetson runs with target profile difference plus target-comparison smoke
- `scripts/smoke_jetson_sampled_conditional_compare.sh` — provider-difference sampled conditional compare smoke
- `examples/profiles/jetson_nano_sampled_local.yaml` — baseline optional `jetson-tegrastats` sampler profile
- `examples/benches/jetson_sampled_local.yaml` — sampled benchmark config
- `docs/jetson-sampled-conditional-comparison-rehearsal.md` — runtime/provider conditional comparison record
- `docs/compare-workflow-guide.md` — compare output interpretation rules

기술 스택: Jetson Linux, `tegrastats`, EdgeEnv local runner, SQLite registry, `report compare`

## 3. HOW — 리허설 절차

From the repo root on Jetson:

```bash
scripts/smoke_jetson_sampled_target_compare.sh --python /home/${JETSON_USER}/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

What the script checks:

- runtime dependencies and `tegrastats` are available
- sampled Jetson benchmark config validates
- a temporary target profile changes `target_name` and adds a `target-variant` runtime tag
- two successful sampled runs are stored in the same local registry root
- both runs have the same runtime identity and benchmark protocol
- both runs have different target identities
- both runs have `resource_metrics.source=jetson-tegrastats`
- both runs have sampler metadata and raw sampler artifacts
- `report compare <run_id_a> <run_id_b>` prints `Comparable: Conditional`
- compare mode is `target-comparison`
- compare reason includes `Different target`
- `Metrics Delta` is absent for the conditional target comparison
- compare output does not mention `resource` or `sampler` as a judgement gate

By default the script uses temporary `/tmp/InferEdgeEnv-jetson-sampled-target-*`
directories and deletes only those temporary directories on success. If you pass
a custom `--edgeenv-root`, it must not already exist and will not be deleted
automatically.

Manual equivalent:

```bash
export PYTHONPATH="$PWD"
edgeenv_root=/tmp/InferEdgeEnv-jetson-sampled-target/.edgeenv
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$edgeenv_root"
# Create a temporary copy of examples/profiles/jetson_nano_sampled_local.yaml with target_name changed.
edgeenv bench run --target /tmp/jetson_nano_sampled_target_variant.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$edgeenv_root"
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root "$edgeenv_root"
```

## 4. HOW NOT — 피해야 할 함정

- Do not print latency/throughput `Metrics Delta` for target-comparison reports.
- Do not use sampled power, memory, temperature, or sampler metadata to override the target-comparison judgement.
- Do not change runtime/provider or required benchmark protocol fields for this rehearsal; the point is target identity difference.
- Do not describe this as remote execution support; the run still happens locally on Jetson.
- Do not commit generated `.edgeenv/`, temporary target profiles, zip exports, raw `tegrastats` logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Compare Workflow Guide**: this validates the target conditional branch with real sampled evidence.
- **Jetson Sampled Conditional Comparison Rehearsal**: this complements the runtime/provider conditional branch.
- **Jetson Environment Setup Hardening**: reuses the source snapshot + known Python environment pattern.
- **Sampler Metadata Artifact Policy**: sampler metadata remains artifact evidence, not a compare gate.

## 6. WHY — 배경 판단

Runtime/provider conditional compare prevents direct regression claims across runtime changes. Target-comparison does the same for platform identity changes. This rehearsal verifies the target branch with real Jetson sampled evidence while keeping runtime and benchmark protocol fixed.

That distinction matters because sampled platform evidence can look compelling, but target identity still changes the interpretation mode before any metric number is considered.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Target sampled compare should assert that runtime identity remains unchanged while target identity differs.

## Validation Record — jetson-device

Status: passed on `jetson-device`.

Command:

```bash
scripts/smoke_jetson_sampled_target_compare.sh --python /home/${JETSON_USER}/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

Observed run ids:

```text
run-20260508-022504-83d05a65
run-20260508-022506-aa9d5adf
```

Observed `report compare`:

```text
Comparable: Conditional
Mode: target-comparison
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
- Different target
```

Observed sampled evidence:

```json
{
  "run-20260508-022504-83d05a65": {
    "target_name": "jetson-nano-sampled-local",
    "runtime": {
      "runtime": "local-python",
      "execution_provider": "jetson-cpu-demo"
    },
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 916.667,
      "memory_peak_mb": 917.0,
      "power_mean_w": 4.462,
      "power_peak_w": 4.515,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 41.562
    }
  },
  "run-20260508-022506-aa9d5adf": {
    "target_name": "jetson-nano-sampled-local-target-variant",
    "runtime": {
      "runtime": "local-python",
      "execution_provider": "jetson-cpu-demo"
    },
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 911.0,
      "memory_peak_mb": 912.0,
      "power_mean_w": 4.442,
      "power_peak_w": 4.482,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 41.437
    }
  }
}
```

Conclusion:

- Both runs had valid `jetson-tegrastats` resource metrics and sampler artifacts.
- The required benchmark protocol, model identity, runtime, and execution provider matched.
- The second run changed target profile metadata to `jetson-nano-sampled-local-target-variant`.
- `report compare` reported `Comparable: Conditional` with `Mode: target-comparison`.
- `Metrics Delta` was absent, as required for target comparisons.
- Resource and sampler evidence did not appear as compare judgement reasons.
