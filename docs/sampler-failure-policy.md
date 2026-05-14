# Sampler Failure Policy

> Language: [English overview](language.md#english-overview) | [한국어/원문](#)

## 1. WHAT — 이 문서가 정하는 것

Wrapper command나 future sampler adapter에서 resource sampling이 실패했을 때, benchmark run 전체를 실패로 볼지 아니면 resource metrics 없이 성공 run으로 저장할지 기준을 정한다.

핵심 원칙은 단순하다. Primary benchmark metrics가 유효하면 성공 run을 보존한다. Resource metrics는 optional secondary evidence이므로, sampler 실패만으로 benchmark result를 버리지 않는다.

## 2. CONTENTS — 관련 파일과 기술 스택

관련 파일:

- `inferedge_env/runners/local.py` — command exit code와 explicit JSON contract를 검증한다.
- `inferedge_env/result/writer.py` — 성공 run과 failed-run artifact를 분리한다.
- `docs/local-runner-design.md` — local command failure artifact 기준
- `docs/resource-metrics-design.md` — resource metrics는 optional evidence라는 기준
- `docs/platform-sampler-design.md` — wrapper command first sampler integration
- `docs/sampler-adapter-api-design.md` — future adapter failure taxonomy
- `examples/scripts/run_with_sampler.py` — deterministic wrapper command example
- `examples/scripts/run_with_sampler_failure_modes.py` — sampler unavailable / malformed resource metrics examples

기술 스택: stdout/stderr contract, JSON artifact, failed-run artifact

## 3. HOW — 정책

### Benchmark failure

아래 경우에는 benchmark run 전체를 실패로 본다.

- benchmark command가 non-zero exit code로 종료된다.
- `EDGEENV_METRICS_JSON=` line이 없다.
- `EDGEENV_METRICS_JSON=` JSON이 깨져 있다.
- primary metrics schema가 틀리다.
- wrapper가 benchmark command의 primary metrics를 잃어버리거나 바꿔치기한다.

이 경우 `.edgeenv/failed-runs/<run_id>/`에 failure artifact를 남기고 `.edgeenv/runs.db`에는 insert하지 않는다.

### Successful run without resource metrics

아래 경우에는 benchmark run은 성공으로 저장하고, resource metrics는 생략할 수 있다.

- sampler tool이 없거나 권한이 없다.
- sampler process가 시작되지 않았다.
- sampler output이 비어 있다.
- sampler output은 있었지만 summary를 만들 수 없다.
- sampler timeout이 benchmark measurement 자체에는 영향을 주지 않았다.

이 경우 wrapper/adaptor는 `EDGEENV_METRICS_JSON=`를 그대로 출력하고, `EDGEENV_RESOURCE_METRICS_JSON=`를 출력하지 않는다. `result.json`에는 `resource_metrics` field가 생략된다.
CLI는 이 상태를 `Resource metrics: omitted`으로 표시한다.

### Failed run caused by invalid resource metrics

아래 경우에는 resource evidence가 오염됐다고 보고 benchmark run을 실패로 둔다.

- wrapper/adaptor가 `EDGEENV_RESOURCE_METRICS_JSON=`를 출력했지만 JSON이 깨져 있다.
- resource metrics schema에 없는 field를 출력한다.
- unit이 섞인 값을 unit suffix 없는 field에 넣는다.
- numeric field에 string이나 non-finite value를 넣는다.

현재 `LocalRunner`는 `EDGEENV_RESOURCE_METRICS_JSON=` line이 있으면 schema validation을 수행한다. 따라서 잘못된 resource metrics line을 출력하는 wrapper는 실패한다. 확신이 없으면 line을 출력하지 않는 것이 맞다.
CLI는 failed-run artifact path와 `Registry: not updated`를 표시한다.

실패 원인 확인은 성공 run registry가 아니라 failed-run artifact inspection command를 사용한다.

```bash
edgeenv failed-runs list
edgeenv failed-runs show <run_id>
```

### Wrapper command behavior

Wrapper command는 다음 순서를 지켜야 한다.

```text
1. benchmark command 실행
2. benchmark stdout/stderr 보존
3. benchmark exit code 확인
4. EDGEENV_METRICS_JSON= line 확인
5. sampler summary가 신뢰 가능할 때만 EDGEENV_RESOURCE_METRICS_JSON= 출력
6. EDGEENV_METRICS_JSON= line 출력
```

Wrapper가 sampler 실패를 diagnostic log로 남기고 싶다면 일반 stdout/stderr log에 남긴다. 하지만 `EDGEENV_RESOURCE_METRICS_JSON=` line은 schema-valid evidence를 만들 수 있을 때만 출력한다.

## 4. HOW NOT — 피해야 할 함정

- sampler 실패만으로 primary benchmark result를 버리지 않는다.
- 깨진 sampler output을 `resource_metrics`에 억지로 넣지 않는다.
- `resource_metrics`가 없다는 이유로 old run이나 sampler 없는 run을 낮은 품질 run으로 표시하지 않는다.
- wrapper가 child benchmark의 primary metrics를 재계산하거나 추정하지 않는다.
- sampler failure를 성공 resource evidence처럼 보이게 만들지 않는다.
- failed-run artifact를 성공 run registry에 insert하지 않는다.

## 5. WHERE — 다른 설계와의 관계

- **Local Runner Design**: command exit code와 primary metrics validation이 run success/failure의 기준이다.
- **Resource Metrics Design**: resource metrics는 optional secondary evidence다.
- **Platform Sampler Design**: wrapper command는 sampler 실패를 처리한 뒤 명시적 stdout contract를 출력한다.
- **Registry Resource Query Design**: resource metrics가 없는 성공 run도 valid run이다.
- **Comparability**: resource metrics 유무는 direct comparability gate가 아니다.

## 6. WHY — 배경 판단

EdgeEnv의 핵심 evidence는 primary benchmark protocol과 latency/throughput metrics다. Resource sampling은 유용하지만 platform 권한과 측정 환경에 민감하다. sampler 실패만으로 benchmark result를 버리면 로컬 evidence 보존성이 떨어진다.

반대로 깨진 resource metrics를 성공 run에 넣으면 evidence 신뢰도가 더 크게 깨진다. 그래서 정책은 "모르면 생략하고, 출력했으면 검증한다"이다.

## 7. ⚠️ LEARNED CAUTIONS — 학습된 주의사항

_(아직 없음)_

## Implementation Checklist

- [x] wrapper example for sampler unavailable but benchmark succeeds
- [x] wrapper example for malformed resource metrics failure
- [x] failed-run artifact test for invalid resource metrics
- [x] future sampler adapter error taxonomy
