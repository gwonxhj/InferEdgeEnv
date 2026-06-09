# Runtime Regression Monitor 한국어 Quick Guide

> Language: [English representative](../compare-workflow-guide.md#runtime-regression-report) | 한국어

이 문서는 EdgeEnv의 runtime regression monitor 역할을 한국어로 빠르게
확인하기 위한 안내서다. 대표 영어 경로는
[Compare Workflow Guide의 Runtime Regression Report](../compare-workflow-guide.md#runtime-regression-report)이다.

## 핵심 정의

EdgeEnv는 단순 benchmark runner가 아니다. EdgeEnv는 local-first run evidence
registry와 comparability checker를 기반으로 comparability-first runtime
regression evidence를 생성하는 layer다.

```text
run result
-> registry 저장
-> comparability check
-> regression analysis
-> report
```

EdgeEnv는 먼저 두 run이 비교 가능한지 판단한다. 비교 가능한 경우에만
latency/resource regression delta를 계산한다. 비교 조건이 맞지 않으면
regression을 계산하지 않고, 왜 비교하면 안 되는지 evidence로 남긴다.

## Comparability-first 기준

Regression 계산 전에 아래 조건은 같아야 한다.

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

`runtime`, `provider`, `target`이 다르면 같은 조건 regression으로 보지 않는다.
대신 각각 `runtime-comparison`, `target-comparison`으로 표시한다.

Benchmark protocol mismatch가 있으면 `protocol_mismatch`로 표시하고 regression
계산을 금지한다.

## Report mode 해석

| Mode | 의미 | Regression delta |
| --- | --- | --- |
| `same-condition` | 모델, 입력, precision, protocol이 같은 직접 비교 | 계산 가능 |
| `runtime-comparison` | runtime/provider가 다른 비교 | 계산 금지 |
| `target-comparison` | device, target, power profile이 다른 비교 | 계산 금지 |
| `protocol_mismatch` | warmup/repeat/preprocess 같은 protocol이 다름 | 계산 금지 |

## Regression evidence

EdgeEnv가 same-condition에서 계산하는 주요 evidence는 다음과 같다.

- mean latency regression
- p95 / p99 tail latency regression
- FPS drop
- memory peak regression
- optional thermal / power evidence context

기본 starter threshold는 아래 기준으로 해석한다.

| Signal | Starter threshold | 의미 |
| --- | ---: | --- |
| Mean latency | +15% | review |
| P99 latency | +25% | review / high severity |
| FPS | -20% | review |
| Memory peak | +30% | warning |

이 threshold는 local policy 기준이며, production SaaS alerting이나 cloud
monitoring policy가 아니다.

## 역할 경계

- EdgeEnv는 registry, comparability judgement, runtime regression evidence를
  소유한다.
- EdgeEnv는 Lab `deployment_decision`을 만들거나 덮어쓰지 않는다.
- EdgeEnv는 AIGuard `guard_analysis`를 생성하지 않는다.
- EdgeEnv는 Orchestrator scheduler, queue/drop/fallback owner가 아니다.
- Runtime telemetry, Orchestrator feed, resource metrics는 supplemental
  evidence이며 comparability gate를 우회하지 않는다.
- EdgeEnv는 production observability platform, general monitoring SaaS,
  public leaderboard, cloud control plane이 아니다.
- Real-time data drift는 현재 범위가 아니라 future work 또는 별도 validation
  topic이다.

## Jetson 필요 여부

이 문서를 읽거나 committed replay fixture, JSON/Markdown report link를
검증하는 작업에는 Jetson 기기가 필요 없다.

새 Jetson runtime output, live telemetry, device-local sustained evidence를
수집해 regression report를 갱신할 때는 Jetson 기기가 필요하다.

## 빠른 확인 경로

```bash
edgeenv report regression <baseline_run_id> <candidate_run_id> \
  --telemetry-history /tmp/edgeenv-runtime-telemetry-history.json \
  --output-json /tmp/edgeenv-regression.json \
  --output-md /tmp/edgeenv-regression.md
```

Downstream AIGuard/Lab handoff를 live device 없이 확인해야 할 때는
`examples/regression/`의 committed replay fixture를 사용한다.
`examples/regression/fixture_matrix.json`은 각 fixture가 어떤 mode를
대표하는지, regression delta 계산이 허용되는지, telemetry gap 또는 replay
sequence context가 필요한지를 기록하는 machine-readable index다.
