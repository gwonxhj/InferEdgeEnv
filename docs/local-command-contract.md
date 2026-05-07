# Local Command Contract Guide

## 1. WHAT — 이 문서가 정하는 것

사용자가 자기 benchmark command를 `target_type: local` runner에 연결할 때 지켜야 하는 stdout contract, config 작성 방식, 실패 원인 진단 기준을 정리한다.

EdgeEnv는 모델을 대신 실행하거나 benchmark log를 추측하지 않는다. Local command가 benchmark를 수행하고, EdgeEnv가 읽을 수 있는 명시적 JSON line을 stdout에 출력해야 한다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/runners/local.py` — local command 실행과 stdout contract parser
- `examples/scripts/local_benchmark_template.py` — 사용자가 복사해 시작할 수 있는 최소 benchmark template
- `examples/benches/local_template.yaml` — template script를 실행하는 benchmark config
- `examples/profiles/local.yaml` — local target profile
- `docs/local-runner-design.md` — local runner 내부 설계
- `docs/resource-metrics-design.md` — optional resource metrics contract
- `docs/sampler-failure-policy.md` — sampler/resource metrics 실패 정책

기술 스택: Python, YAML, stdout JSON line contract

## 3. HOW — command를 연결하는 방법

### Minimal command shape

Benchmark command는 일반 로그를 출력해도 되지만, stdout에 마지막으로 다음 line을 반드시 출력해야 한다.

```text
EDGEENV_METRICS_JSON={"latency_mean_ms":12.3,"latency_p50_ms":12.0,"latency_p95_ms":14.1,"latency_p99_ms":15.0,"throughput_fps":81.3}
```

필수 primary metrics:

- `latency_mean_ms`
- `latency_p50_ms`
- `latency_p95_ms`
- `latency_p99_ms`
- `throughput_fps`

선택적 resource metrics:

```text
EDGEENV_RESOURCE_METRICS_JSON={"memory_peak_mb":512.0,"power_mean_w":8.2,"source":"my-tool"}
```

Resource metrics를 확실히 만들 수 없으면 이 line을 출력하지 않는다. 출력하지 않으면 성공 run은 보존되고 `resource_metrics` field만 생략된다.

### Template flow

```bash
edgeenv bench run --target examples/profiles/local.yaml --config examples/benches/local_template.yaml
edgeenv runs show <run_id>
```

`examples/scripts/local_benchmark_template.py`는 다음을 보여준다.

- EdgeEnv가 주입한 `EDGEENV_*` environment variable 읽기
- command-specific `extra_env` 읽기
- 실제 측정 부분을 넣을 위치
- primary metrics JSON line 출력
- optional resource metrics JSON line 출력

### Benchmark config checklist

- `command`는 현재 머신에서 바로 실행 가능한 command여야 한다.
- quote가 필요한 path는 shell quoting을 config에 명시한다.
- `working_directory`를 쓰면 command는 그 directory에서 실행된다.
- `timeout_seconds`는 command 전체 timeout이다.
- `extra_env` key는 uppercase여야 하며 `EDGEENV_` prefix를 쓸 수 없다.
- `warmup_runs`와 `repeat_runs`는 EdgeEnv가 subprocess를 반복한다는 뜻이 아니다. command 내부 benchmark loop가 이 protocol을 따라야 한다.

### Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `Missing EDGEENV_METRICS_JSON=<json> line in stdout` | command가 primary metrics line을 출력하지 않았다 | 마지막 stdout line 중 하나에 `EDGEENV_METRICS_JSON=`를 출력한다 |
| `Invalid EDGEENV_METRICS_JSON JSON` | JSON quoting, comma, brace가 깨졌다 | `json.dumps(...)` 같은 structured JSON writer를 사용한다 |
| `Invalid local metrics schema` | 필수 latency/throughput field가 빠졌거나 값 type이 틀렸다 | 필수 primary metrics 5개를 numeric 값으로 출력한다 |
| `Invalid EDGEENV_RESOURCE_METRICS_JSON JSON` | optional resource metrics JSON이 깨졌다 | 확실히 만들 수 없으면 line을 출력하지 않는다 |
| `Invalid local resource metrics schema` | 알 수 없는 field나 잘못된 type을 출력했다 | `ResourceMetrics` schema의 unit-suffixed field만 사용한다 |
| `Local benchmark command failed with exit code N` | benchmark command 자체가 실패했다 | `edgeenv failed-runs list`로 run ID를 찾고 `edgeenv failed-runs show <run_id>`로 stdout/stderr를 확인한다 |
| `Local benchmark command timed out after ... seconds` | `timeout_seconds` 안에 command가 끝나지 않았다 | benchmark loop를 줄이거나 timeout을 늘린다 |
| `Failed to start local benchmark command` | command path가 없거나 실행할 수 없다 | `command`, `working_directory`, virtualenv/path를 확인한다 |

## 4. HOW NOT — 피해야 할 함정

- 일반 log에서 latency 숫자를 출력하는 것만으로 충분하다고 가정하지 않는다.
- `EDGEENV_METRICS_JSON=`를 stderr에 출력하지 않는다. Local runner는 stdout contract를 읽는다.
- 사람이 직접 JSON 문자열을 이어 붙이지 않는다. 가능한 structured JSON writer를 쓴다.
- resource metrics를 모를 때 placeholder string이나 unit suffix가 붙은 string을 출력하지 않는다.
- benchmark 실패를 숨기고 성공 metrics처럼 출력하지 않는다.
- Docker, WSL, SSH 실행을 local command guide의 기본 경로로 설명하지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Local Runner Design**: 이 문서는 local runner 설계를 사용자-facing contract로 옮긴다.
- **Resource Metrics Design**: optional resource metrics의 field와 저장 정책을 따른다.
- **Sampler Failure Policy**: sampler/resource evidence가 불확실하면 생략하고, 출력했다면 검증한다.
- **Registry Resource Query Design**: resource metrics는 현재 DB column 없이 artifact에서 읽는다.

## 6. WHY — 배경 판단

EdgeEnv의 비교 가능성은 benchmark log parser의 영리함이 아니라 명시적 evidence contract에서 나온다. 사용자가 command 안에서 자신의 runtime, model, input, measurement loop를 통제하고, EdgeEnv는 그 결과를 검증 가능한 artifact로 고정한다.

이 문서는 실제 command를 붙이는 순간 헷갈리기 쉬운 부분을 줄여 local runner가 "예제는 되는데 내 command는 안 된다" 상태에 머무르지 않게 한다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_
