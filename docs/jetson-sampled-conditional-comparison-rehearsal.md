# Jetson Sampled Conditional Comparison Rehearsal

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Jetson에서 `sampler: jetson-tegrastats`가 켜진 sampled local run 두 개를 생성하되, 두 번째 run의 `execution_provider`만 의도적으로 다르게 만들어 `report compare`가 `Comparable: Conditional`을 출력하고 metric delta를 숨기는지 확인한다.

이 리허설은 sampler/resource evidence가 있어도 runtime/provider 차이가 직접 회귀 비교로 해석되지 않아야 한다는 compare 계약을 실제 Jetson evidence로 검증한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `scripts/smoke_jetson_sampled_conditional_compare.sh` — two sampled Jetson runs with provider difference plus conditional compare smoke
- `scripts/smoke_jetson_sampled_compare.sh` — same-condition sampled compare smoke
- `examples/profiles/jetson_nano_sampled_local.yaml` — optional `jetson-tegrastats` sampler profile
- `examples/benches/jetson_sampled_local.yaml` — baseline sampled benchmark config
- `docs/jetson-sampled-comparison-rehearsal.md` — same-condition sampled comparison record
- `docs/compare-workflow-guide.md` — compare output interpretation rules

기술 스택: Jetson Linux, `tegrastats`, EdgeEnv local runner, SQLite registry, `report compare`

## 3. HOW — 리허설 절차

From the repo root on Jetson:

```bash
scripts/smoke_jetson_sampled_conditional_compare.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

What the script checks:

- runtime dependencies and `tegrastats` are available
- sampled Jetson profile/config validate
- a temporary benchmark config changes only `name` and `execution_provider`
- two successful sampled runs are stored in the same local registry root
- both runs have sampler metadata and raw sampler artifacts
- both runs have `resource_metrics.source=jetson-tegrastats`
- `report compare <run_id_a> <run_id_b>` prints `Comparable: Conditional`
- compare mode is `runtime-comparison`
- compare reason includes `Different runtime or execution provider`
- `Metrics Delta` is absent for the conditional comparison
- compare output does not mention `resource` or `sampler` as a judgement gate

By default the script uses temporary `/tmp/InferEdgeEnv-jetson-sampled-conditional-*`
directories and deletes only those temporary directories on success. If you pass
a custom `--edgeenv-root`, it must not already exist and will not be deleted
automatically.

Manual equivalent:

```bash
export PYTHONPATH="$PWD"
edgeenv_root=/tmp/InferEdgeEnv-jetson-sampled-conditional/.edgeenv
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config examples/benches/jetson_sampled_local.yaml --edgeenv-root "$edgeenv_root"
# Create a temporary copy of examples/benches/jetson_sampled_local.yaml with execution_provider changed.
edgeenv bench run --target examples/profiles/jetson_nano_sampled_local.yaml --config /tmp/jetson_sampled_provider_variant.yaml --edgeenv-root "$edgeenv_root"
edgeenv report compare <run_id_a> <run_id_b> --edgeenv-root "$edgeenv_root"
```

## 4. HOW NOT — 피해야 할 함정

- Do not print latency/throughput `Metrics Delta` for conditional comparisons.
- Do not use sampled power, memory, temperature, or sampler metadata to override the conditional judgement.
- Do not change required benchmark protocol fields for this rehearsal; the point is runtime/provider difference.
- Do not describe this as remote execution support; the run still happens locally on Jetson.
- Do not commit generated `.edgeenv/`, temporary config copies, zip exports, raw `tegrastats` logs, models, engines, or datasets.

## 5. WHERE — 다른 설계와의 관계

- **Compare Workflow Guide**: this validates the conditional runtime/provider branch with real sampled evidence.
- **Jetson Sampled Comparison Rehearsal**: this complements the same-condition sampled compare record.
- **Jetson Sampled Target Comparison Rehearsal**: this complements the target conditional branch.
- **Jetson Environment Setup Hardening**: reuses the source snapshot + known Python environment pattern.
- **Sampler Metadata Artifact Policy**: sampler metadata remains artifact evidence, not a compare gate.

## 6. WHY — 배경 판단

Same-condition sampled runs prove that sampler evidence does not pollute direct comparisons. Conditional sampled runs prove the inverse: even when both runs have valid sampler evidence and identical required benchmark protocol, a runtime/provider difference still changes the interpretation mode and suppresses direct metric deltas.

That distinction keeps EdgeEnv from accidentally turning sampled platform evidence into a single-score ranking or an unsupported regression claim.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

- Conditional sampled compare should assert that `Metrics Delta` is absent and resource/sampler evidence is absent from compare reasons.

## Validation Record — nano01

Status: passed on `nano01`.

Command:

```bash
scripts/smoke_jetson_sampled_conditional_compare.sh --python /home/risenano01/miniconda3/envs/yolo_env/bin/python --keep-artifacts
```

Observed run ids:

```text
run-20260508-020901-a0cf9cf8
run-20260508-020904-21a7fa6b
```

Observed `report compare`:

```text
Comparable: Conditional
Mode: runtime-comparison
Reason:
- Same model hash
- Same input shape
- Same precision
- Same benchmark protocol
- Different runtime or execution provider
```

Observed sampled evidence:

```json
{
  "run-20260508-020901-a0cf9cf8": {
    "execution_provider": "jetson-cpu-demo",
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 907.667,
      "memory_peak_mb": 909.0,
      "power_mean_w": 4.462,
      "power_peak_w": 4.515,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 41.937
    }
  },
  "run-20260508-020904-21a7fa6b": {
    "execution_provider": "jetson-cpu-demo-variant",
    "sample_count": 3,
    "raw_artifacts": ["sampler/tegrastats.log"],
    "resource_metrics": {
      "memory_mean_mb": 910.667,
      "memory_peak_mb": 911.0,
      "power_mean_w": 4.442,
      "power_peak_w": 4.482,
      "source": "jetson-tegrastats",
      "temperature_peak_c": 42.093
    }
  }
}
```

Conclusion:

- Both runs had valid `jetson-tegrastats` resource metrics and sampler artifacts.
- The required benchmark protocol and model identity fields matched.
- The second run changed `execution_provider` to `jetson-cpu-demo-variant`.
- `report compare` reported `Comparable: Conditional` with `Mode: runtime-comparison`.
- `Metrics Delta` was absent, as required for conditional comparisons.
- Resource and sampler evidence did not appear as compare judgement reasons.
