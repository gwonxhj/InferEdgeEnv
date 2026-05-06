# Local Runner Design

## 1. WHAT — local runner가 하는 일

`LocalRunner`는 `target_type: local` profile을 대상으로 현재 머신에서 benchmark command를 실행하고, command가 명시적으로 내보낸 metrics JSON을 EdgeEnv `RunnerResult`로 변환한다.

이 설계의 목적은 real local execution을 추가하되, MVP v1의 result JSON, registry, comparability contract를 깨뜨리지 않는 것이다.

## 2. CONTENTS — 대상 파일과 기술 스택

구현 파일:

- `inferedge_env/runners/local.py` — subprocess 기반 local command runner
- `inferedge_env/runners/base.py` — runner result contract 유지
- `inferedge_env/cli.py` — `target_type: local`일 때 `LocalRunner` 선택
- `tests/test_local_runner.py` — command contract, failure handling, stdout/stderr capture 검증
- `examples/benches/local_echo_metrics.yaml` — local runner smoke용 작은 예시
- `examples/profiles/local.yaml` — local target profile 예시
- `examples/scripts/emit_local_metrics.py` — local runner smoke command fixture

기술 스택: Python standard library `subprocess`, `shlex`, `json`, `os`, pytest

## 3. HOW — 구현 방향

### Runner selection

`bench run`은 target profile에 따라 runner를 선택한다.

- `fake` -> `FakeRunner`
- `local` -> `LocalRunner`

`ssh`, `wsl`, `docker`는 계속 미구현으로 남긴다.

### Command execution contract

`LocalRunner`는 `BenchmarkConfig.command`를 현재 머신에서 실행한다. command는 benchmark를 수행한 뒤 stdout에 다음 한 줄을 반드시 출력한다.

```text
EDGEENV_METRICS_JSON={"latency_mean_ms":12.3,"latency_p50_ms":12.0,"latency_p95_ms":14.1,"latency_p99_ms":15.0,"throughput_fps":81.3}
```

규칙:

- `LocalRunner`는 일반 로그를 임의로 추론하지 않는다.
- 마지막으로 발견한 `EDGEENV_METRICS_JSON=` line만 metrics source로 사용한다.
- JSON에는 기존 `RunnerResult` metrics 필드가 모두 있어야 한다.
- stdout/stderr 전체는 기존 artifact writer가 그대로 저장한다.
- command exit code가 non-zero이면 benchmark run은 실패한다.
- metrics line이 없거나 schema가 틀리면 benchmark run은 실패한다.
- 실패한 local run은 `.edgeenv/failed-runs/<run_id>/`에 diagnostic artifact를 남기고, `.edgeenv/runs.db`에는 insert하지 않는다.

### Environment variables

`LocalRunner`는 command에 다음 environment variables를 제공한다.

- `EDGEENV_BENCHMARK_NAME`
- `EDGEENV_MODEL_NAME`
- `EDGEENV_MODEL_PATH`
- `EDGEENV_RUNTIME`
- `EDGEENV_EXECUTION_PROVIDER`
- `EDGEENV_PRECISION`
- `EDGEENV_BATCH_SIZE`
- `EDGEENV_WARMUP_RUNS`
- `EDGEENV_REPEAT_RUNS`
- `EDGEENV_INCLUDE_PREPROCESS`
- `EDGEENV_INCLUDE_POSTPROCESS`
- `EDGEENV_TARGET_NAME`

이 값들은 command가 내부 benchmark loop를 구성할 때 사용할 수 있다.

### Process model

초기 구현은 과도한 shell behavior를 피한다.

- `shlex.split(config.command)`로 argv를 구성한다.
- `subprocess.run(..., shell=False, capture_output=True, text=True)`를 사용한다.
- working directory는 사용자가 CLI를 실행한 현재 directory를 따른다.
- timeout, cwd, extra env schema는 v1.1 이후 검토한다.

## 4. HOW NOT — 피해야 할 함정

- Shell string을 `shell=True`로 실행하지 않는다 — quoting과 shell injection risk가 커진다.
- stdout 전체에서 숫자를 추측하지 않는다 — benchmark tool마다 로그 형식이 달라 오판된다.
- EdgeEnv가 process startup time을 latency로 자동 측정하지 않는다 — 모델 inference latency가 아니라 process overhead를 재게 된다.
- `warmup_runs`와 `repeat_runs`를 LocalRunner가 subprocess 반복 횟수로 해석하지 않는다 — command 내부에서 같은 protocol로 측정해야 p50/p95/p99가 의미 있다.
- 실패 run을 registry에 성공 run처럼 insert하지 않는다 — local registry의 evidence 신뢰도가 깨진다.
- local runner를 Docker/WSL/SSH 실행기로 확장하지 않는다 — target boundary가 흐려진다.

## 5. WHERE — 기존 모듈과의 의존성

- **의존**: `BenchmarkConfig`, `TargetProfile`, `RunnerResult`
- **피의존**: CLI `bench run`, result writer, registry, tests
- **경계 / 어댑터**: external local benchmark command와 EdgeEnv result schema 사이의 adapter

영향 없는 contract:

- `result.json` schema version: `edgeenv.result.v1` 유지
- `.edgeenv/runs/<run_id>/` artifact layout 유지
- `.edgeenv/runs.db` registry columns 유지
- comparability required fields 유지

실패 artifact layout:

```text
.edgeenv/
  failed-runs/
    <run_id>/
      failure.json
      config.yaml
      target.yaml
      env.json
      stdout.log
      stderr.log
```

`failure.json`은 `edgeenv.failed-run.v1` schema marker, command, error message, return code, benchmark name, target name을 담는다.

## 6. WHY — 배경 판단

local runner에서 가장 위험한 선택은 "아무 command나 실행하고 로그를 적당히 읽어 latency를 알아낸다"는 방식이다. 그 방식은 처음에는 편해 보이지만, benchmark마다 로그 형식이 다르고 process startup overhead와 inference latency가 섞여 비교 가능성을 망친다.

그래서 v1.1 local runner는 command가 EdgeEnv metrics contract를 명시적으로 출력하게 한다. EdgeEnv는 실행, capture, schema validation, artifact/registry persistence만 담당한다. 이 책임 분리가 EdgeEnv의 목표인 result recording and comparability judgement와 맞다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Implementation Checklist

- [x] `LocalRunner` class 추가
- [x] `EDGEENV_METRICS_JSON=` parser 추가
- [x] non-zero exit code error message 추가
- [x] missing/invalid metrics line error message 추가
- [x] CLI runner selection에서 `local`을 `LocalRunner`로 연결
- [x] local runner smoke example 추가
- [x] failed-run artifact bundle
- [x] pytest:
  - valid command returns deterministic metrics
  - stdout/stderr capture preserved
  - non-zero command fails
  - missing metrics line fails
  - invalid metrics JSON fails
  - CLI `bench run` with local profile succeeds against a tiny Python one-liner or fixture script

## Deferred Work

- command timeout
- explicit working directory field
- extra environment variables allowlist
- richer metric schema such as memory/power
- SSH/WSL/Docker targets
